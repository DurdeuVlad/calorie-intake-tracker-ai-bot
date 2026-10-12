import { fireEvent, render, screen } from '@testing-library/react-native';

import { AuthForm } from '../src/components/AuthForm';

describe('AuthForm', () => {
  it('shows field errors and does not submit on invalid input', async () => {
    const onSubmit = jest.fn();
    await render(<AuthForm submitLabel="Sign in" onSubmit={onSubmit} />);

    await fireEvent.changeText(screen.getByTestId('email-input'), 'not-an-email');
    await fireEvent.changeText(screen.getByTestId('password-input'), 'short');
    await fireEvent.press(screen.getByTestId('submit-button'));

    expect(screen.getByTestId('email-error')).toBeOnTheScreen();
    expect(screen.getByTestId('password-error')).toBeOnTheScreen();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('requires a non-empty email', async () => {
    const onSubmit = jest.fn();
    await render(<AuthForm submitLabel="Sign in" onSubmit={onSubmit} />);

    await fireEvent.press(screen.getByTestId('submit-button'));

    expect(screen.getByTestId('email-error')).toBeOnTheScreen();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits the raw email and password when valid', async () => {
    const onSubmit = jest.fn();
    await render(<AuthForm submitLabel="Sign in" onSubmit={onSubmit} />);

    await fireEvent.changeText(screen.getByTestId('email-input'), 'user@example.com');
    await fireEvent.changeText(screen.getByTestId('password-input'), 'password123');
    await fireEvent.press(screen.getByTestId('submit-button'));

    expect(onSubmit).toHaveBeenCalledWith('user@example.com', 'password123');
    expect(screen.queryByTestId('email-error')).toBeNull();
    expect(screen.queryByTestId('password-error')).toBeNull();
  });

  it('surfaces a server error above the button', async () => {
    await render(
      <AuthForm submitLabel="Sign in" onSubmit={jest.fn()} error="invalid email or password" />,
    );
    expect(screen.getByTestId('server-error')).toHaveTextContent('invalid email or password');
  });

  it('disables inputs and shows a spinner while loading', async () => {
    await render(<AuthForm submitLabel="Sign in" onSubmit={jest.fn()} loading />);

    expect(screen.getByTestId('submit-spinner')).toBeOnTheScreen();
    expect(screen.getByTestId('submit-button')).toBeDisabled();
    expect(screen.getByTestId('email-input').props.editable).toBe(false);
    expect(screen.getByTestId('password-input').props.editable).toBe(false);
  });
});
