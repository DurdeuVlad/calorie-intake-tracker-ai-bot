ALTER TABLE messaging_outbox ADD COLUMN legacy_outbound_id BIGINT UNIQUE;

INSERT INTO messaging_outbox (provider, conversation_id, text, status, attempts, next_attempt_at, legacy_outbound_id)
SELECT 'telegram', chat_id::text, text, 'PENDING', attempts, current_timestamp, id
FROM outbound_telegram_messages
WHERE status <> 'SENT'
ON CONFLICT (legacy_outbound_id) DO NOTHING;

UPDATE outbound_telegram_messages SET status = 'SENT', sent_at = COALESCE(sent_at, current_timestamp)
WHERE status <> 'SENT';

INSERT INTO messaging_inbox (provider, event_id, payload, status, attempts, next_attempt_at)
SELECT 'telegram', update_id::text,
  jsonb_build_object(
    'provider','telegram', 'eventId',update_id::text, 'userId',telegram_user_id::text,
    'conversationId',chat_id::text, 'displayName','Telegram user', 'languageCode',NULL,
    'text',payload::jsonb #>> '{message,text}',
    'caption',payload::jsonb #>> '{message,caption}',
    'attachments',CASE WHEN payload::jsonb #>> '{message,voice,file_id}' IS NOT NULL
      THEN jsonb_build_array(jsonb_build_object('kind','VOICE','handle',payload::jsonb #>> '{message,voice,file_id}','mimeType',payload::jsonb #>> '{message,voice,mime_type}','name',NULL))
      WHEN payload::jsonb #>> '{message,photo,-1,file_id}' IS NOT NULL
      THEN jsonb_build_array(jsonb_build_object('kind','PHOTO','handle',payload::jsonb #>> '{message,photo,-1,file_id}','mimeType','image/jpeg','name',NULL))
      WHEN payload::jsonb #>> '{message,document,file_id}' IS NOT NULL
      THEN jsonb_build_array(jsonb_build_object('kind','DOCUMENT','handle',payload::jsonb #>> '{message,document,file_id}','mimeType',payload::jsonb #>> '{message,document,mime_type}','name',payload::jsonb #>> '{message,document,file_name}'))
      ELSE '[]'::jsonb END),
  'PENDING', attempts, current_timestamp
FROM telegram_update_inbox
WHERE status IN ('PENDING','IN_PROGRESS') AND payload::jsonb ? 'message'
ON CONFLICT (provider,event_id) DO NOTHING;

UPDATE telegram_update_inbox SET status = 'COMPLETED', payload = '', completed_at = COALESCE(completed_at,current_timestamp)
WHERE status IN ('PENDING','IN_PROGRESS');
