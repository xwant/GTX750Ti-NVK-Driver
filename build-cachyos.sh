#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
work=${GM107_WORKDIR:-"$root/work"}
sha=8e87a503ebd91408c88596d1b9eeb5f4c0b2088d
jobs=${GM107_JOBS:-4}
for tool in git cc c++ meson ninja rustc rustfmt bindgen cbindgen pkg-config python3; do
  command -v "$tool" >/dev/null || { echo "Missing build tool: $tool; see README_RU.md" >&2; exit 1; }
done
mkdir -p "$work" "$root/logs"
if [[ ! -d "$work/mesa-base" ]]; then
  git clone --depth 1 --branch mesa-26.2.6 https://gitlab.freedesktop.org/mesa/mesa.git "$work/mesa-base"
fi
[[ $(git -C "$work/mesa-base" rev-parse HEAD) == "$sha" ]] || { echo "Unexpected base commit" >&2; exit 1; }
git -C "$work/mesa-base" diff --exit-code
git -C "$work/mesa-base" diff --cached --exit-code
patchsum=$(sha256sum "$root/gm107-command-cache.patch" | cut -d " " -f 1)
if [[ ! -d "$work/mesa-patched" ]]; then
  git -C "$work/mesa-base" worktree add -b experiment/gm107-command-cache "$work/mesa-patched" "$sha"
  git -C "$work/mesa-patched" apply --check "$root/gm107-command-cache.patch"
  git -C "$work/mesa-patched" apply "$root/gm107-command-cache.patch"
  printf "%s\n" "$patchsum" > "$work/patch.sha256"
fi
[[ -f "$work/patch.sha256" && $(cat "$work/patch.sha256") == "$patchsum" ]] || {
  echo "Existing patched tree does not match this experiment; use a fresh GM107_WORKDIR" >&2; exit 1;
}
git -C "$work/mesa-patched" apply --reverse --check "$root/gm107-command-cache.patch"
pacman -Q > "$root/logs/cachyos-packages.txt"
uname -a > "$root/logs/cachyos-kernel.txt"
opts=(-Dbuildtype=debugoptimized -Db_ndebug=false -Dplatforms=x11,wayland
      -Dgallium-drivers=[] -Dvulkan-drivers=nouveau -Dglx=disabled
      -Degl=disabled -Dgbm=disabled -Dgles1=disabled -Dgles2=disabled
      -Dopengl=false -Dbuild-tests=true -Dvalgrind=disabled -Dlibunwind=disabled)
for variant in base patched; do
  src="$work/mesa-$variant"
  build="$src/build-gm107"
  if [[ ! -f "$build/build.ninja" ]]; then
    meson setup "$build" "$src" "${opts[@]}" 2>&1 | tee "$root/logs/configure-$variant.log"
  fi
  ninja -C "$build" -j "$jobs" 2>&1 | tee "$root/logs/build-$variant.log"
  meson test -C "$build" --suite nouveau --print-errorlogs 2>&1 | tee "$root/logs/test-$variant.log"
  meson introspect "$build" --buildoptions > "$root/logs/options-$variant.json"
done
cc -std=c11 -O2 -Wall -Wextra -Werror -I "$work/mesa-base/include" \
   "$root/bench/vk_cache_probe.c" -Wl,-l:libvulkan.so.1 -o "$root/bench/vk_cache_probe"
echo "Builds and CPU tests complete. No install, module change, or GPU test was performed."