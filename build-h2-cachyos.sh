#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work=${GM107_H2_WORKDIR:-"$root/work-h2"}; mkdir -p "$work"; work=$(cd "$work" && pwd)
sha=8e87a503ebd91408c88596d1b9eeb5f4c0b2088d
for tool in git cc c++ meson ninja rustc bindgen cbindgen pkg-config python3 glslangValidator spirv-val; do
 command -v "$tool" >/dev/null || { echo "Missing development tool: $tool" >&2; exit 1; }
done
(cd "$root/patches/h2" && sha256sum -c SHA256SUMS)
series=$(sha256sum "$root/patches/h2/SHA256SUMS" | cut -d ' ' -f1)
mkdir -p "$work/logs" "$work/icd" "$work/bin"
if [[ ! -d "$work/mesa-base" ]]; then git clone --depth 1 --branch mesa-26.2.6 https://gitlab.freedesktop.org/mesa/mesa.git "$work/mesa-base"; fi
[[ $(git -C "$work/mesa-base" rev-parse HEAD) == "$sha" ]]
[[ -z $(git -C "$work/mesa-base" status --porcelain --untracked-files=no) ]]
if [[ ! -d "$work/mesa-h2" ]]; then
 git -C "$work/mesa-base" worktree add -b experiment/gm107-ubo-cbuf "$work/mesa-h2" "$sha"
 git -C "$work/mesa-h2" -c user.name='GM107 experiment' -c user.email=gm107@example.invalid am "$root"/patches/h2/*.patch
 git -C "$work/mesa-h2" rev-parse HEAD > "$work/h2-head"
 printf '%s\n' "$series" > "$work/series.sha256"
fi
[[ -f "$work/series.sha256" && $(cat "$work/series.sha256") == "$series" ]] || { echo 'Changed/incomplete patch series: choose a fresh GM107_H2_WORKDIR; no reset performed.' >&2; exit 1; }
[[ $(git -C "$work/mesa-h2" rev-parse HEAD) == $(cat "$work/h2-head") ]]
[[ -z $(git -C "$work/mesa-h2" status --porcelain --untracked-files=no) ]]
! git -C "$work/mesa-h2" grep -q NVK_GM107_CMD_CACHE_LIMIT_KIB -- src/nouveau
opts=(-Dbuildtype=debugoptimized -Db_ndebug=false -Dplatforms=x11,wayland '-Dgallium-drivers=[]' -Dvulkan-drivers=nouveau -Dglx=disabled -Degl=disabled -Dgbm=disabled -Dgles1=disabled -Dgles2=disabled -Dopengl=false -Dbuild-tests=true -Dvalgrind=disabled -Dlibunwind=disabled)
if [[ ${GM107_HEADLESS:-0} == 1 ]]; then opts[2]='-Dplatforms=[]'; fi
for variant in base h2; do
 src="$work/mesa-$variant"; build="$src/build-h2"; config=()
 if [[ -f "$build/build.ninja" ]]; then config=(--reconfigure); fi
 meson setup "${config[@]}" "$build" "$src" "${opts[@]}" 2>&1 | tee "$work/logs/configure-$variant.log"
 target="src/nouveau/vulkan/nouveau_devenv_icd.$(uname -m).json"
 ninja -C "$build" -j "${GM107_JOBS:-4}" src/nouveau/vulkan/libvulkan_nouveau.so "$target" 2>&1 | tee "$work/logs/build-$variant.log"
 meson test -C "$build" --suite nouveau --print-errorlogs -j "${GM107_JOBS:-4}" 2>&1 | tee "$work/logs/tests-$variant.log"
 cp "$build/$target" "$work/icd/$variant.json"
 meson introspect "$build" --buildoptions > "$work/logs/options-$variant.json"
 git -C "$src" rev-parse HEAD > "$work/logs/head-$variant.txt"
 git -C "$src" diff > "$work/logs/dirty-$variant.patch"
 sha256sum "$build/src/nouveau/vulkan/libvulkan_nouveau.so" > "$work/logs/library-$variant.sha256"
done
cc -std=c11 -O2 -Wall -Wextra -Werror "$root/bench/h2/ubo_bench.c" $(pkg-config --cflags --libs vulkan) -o "$work/bin/ubo-bench"
python3 "$root/bench/h2/generate_shaders.py" "$work/shaders"
python3 -m unittest discover -s "$root/bench/h2" -p 'test_*.py'
{ cc --version; meson --version; rustc --version; bindgen --version; cbindgen --version; pkg-config --modversion libdrm vulkan; uname -a; if command -v pacman >/dev/null; then pacman -Q; fi; } > "$work/logs/environment.txt"
(cd "$work/shaders" && sha256sum *.spv) > "$work/logs/shaders.sha256"
printf 'Private builds ready. No install or kernel change.\nSteam C0 launch option:\nbash "%s/bench/h2/run.sh" diag dota-c0 %%command%%\n' "$root"
