#!/usr/bin/env sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
url=$(sed -n 's/^distributionUrl=//p' "$root/.mvn/wrapper/maven-wrapper.properties")
sha512=$(sed -n 's/^distributionSha512=//p' "$root/.mvn/wrapper/maven-wrapper.properties")
file=$(basename "$url")
version=$(printf '%s' "$file" | sed -e 's/^apache-maven-//' -e 's/-bin\.zip$//')
cache="${HOME}/.m2/wrapper/dists/apache-maven-${version}"
home="$cache/apache-maven-$version"
if [ ! -x "$home/bin/mvn" ]; then
  mkdir -p "$cache"
  curl -fsSL "$url" -o "$cache/$file"
  actual=$(sha512sum "$cache/$file" | awk '{print $1}')
  [ "$actual" = "$sha512" ] || { rm -f "$cache/$file"; echo "Maven distribution checksum mismatch." >&2; exit 1; }
  unzip -q "$cache/$file" -d "$cache"
  rm -f "$cache/$file"
fi
exec "$home/bin/mvn" "$@"
