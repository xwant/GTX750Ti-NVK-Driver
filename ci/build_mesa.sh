#!/usr/bin/env bash
# CPU compilation only. Does not install drivers or access the GPU.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
variant=${1:?base|h2|h3|h2-h3}; work=${2:?new-output-directory}; audit=${3:-}; mirror=${4:-}
case "$variant" in base|h2|h3|h2-h3) ;; *) exit 2;; esac
[[ ! -e "$work" ]] || { echo 'Output exists; select a fresh directory.' >&2; exit 2; }
mkdir -p "$work"; work=$(cd "$work" && pwd)
sha=8e87a503ebd91408c88596d1b9eeb5f4c0b2088d
if [[ -n "$mirror" ]]; then
 git clone --no-checkout --shared "$mirror" "$work/mesa"
else
 git clone --depth 1 --branch mesa-26.2.6 https://gitlab.freedesktop.org/mesa/mesa.git "$work/mesa"
fi
git -C "$work/mesa" checkout --detach "$sha"
[[ $(git -C "$work/mesa" rev-parse HEAD) == "$sha" ]]
if [[ "$variant" == h2* ]]; then
 [[ -n "$audit" ]]
 (cd "$audit/patches/h2" && sha256sum -c SHA256SUMS)
 for p in "$audit"/patches/h2/*.patch; do git -C "$work/mesa" apply --index "$p"; done
fi
if [[ "$variant" == *h3 ]]; then
 (cd "$root/patches/h3" && sha256sum -c SHA256SUMS)
 for p in "$root"/patches/h3/*.patch; do git -C "$work/mesa" apply --index "$p"; done
fi
cp "$root/ci/codegen_probe.c" "$work/mesa/src/nouveau/vulkan/test_nvk_codegen_probe.c"
cat >> "$work/mesa/src/nouveau/vulkan/meson.build" <<'EOF'
if with_tests and not with_platform_android
  test('nvk_codegen_probe', executable('test_nvk_codegen_probe',
       files('test_nvk_codegen_probe.c'), dependencies : [nvk_deps],
       link_with : [libnvk]), suite : ['nouveau'])
endif
EOF
platforms='[]'
if [[ ${GM107_WSI:-0} == 1 ]]; then platforms='x11,wayland'; fi
meson setup "$work/build" "$work/mesa" -Dbuildtype=debugoptimized -Db_ndebug=false \
 -Dplatforms="$platforms" '-Dgallium-drivers=[]' -Dvulkan-drivers=nouveau \
 -Dglx=disabled -Degl=disabled -Dgbm=disabled -Dgles1=disabled -Dgles2=disabled \
 -Dopengl=false -Dbuild-tests=true -Dvalgrind=disabled -Dlibunwind=disabled 2>&1 | tee "$work/configure.txt"
ninja -C "$work/build" -j "${GM107_JOBS:-4}" \
 src/nouveau/vulkan/libvulkan_nouveau.so src/nouveau/vulkan/test_nvk_codegen_probe \
 "src/nouveau/vulkan/nouveau_devenv_icd.$(uname -m).json" 2>&1 | tee "$work/build.txt"
meson test -C "$work/build" --suite nouveau --print-errorlogs -j "${GM107_JOBS:-4}" 2>&1 | tee "$work/tests.txt"
NVK_SHADER_TELEMETRY=false "$work/build/src/nouveau/vulkan/test_nvk_codegen_probe" > "$work/codegen-off.txt" 2> "$work/codegen-off.stderr"
[[ ! -s "$work/codegen-off.stderr" ]]
if [[ "$variant" == *h3 ]]; then
 NVK_SHADER_TELEMETRY=true "$work/build/src/nouveau/vulkan/test_nvk_codegen_probe" > "$work/codegen-on.txt" 2> "$work/codegen-on.stderr"
 cmp "$work/codegen-off.txt" "$work/codegen-on.txt"
fi
if [[ "$variant" == h2* ]]; then
 GM107_PROBE_H2=1 NVK_SHADER_TELEMETRY=false "$work/build/src/nouveau/vulkan/test_nvk_codegen_probe" > "$work/codegen-policy-on.txt" 2> "$work/codegen-policy-on.stderr"
 if cmp -s "$work/codegen-off.txt" "$work/codegen-policy-on.txt"; then
  echo 'H2 policy did not affect the compiler probe; cannot test policy-on invariance.' >&2; exit 1
 fi
 if [[ "$variant" == *h3 ]]; then
  GM107_PROBE_H2=1 NVK_SHADER_TELEMETRY=true "$work/build/src/nouveau/vulkan/test_nvk_codegen_probe" > "$work/codegen-policy-diag.txt" 2> "$work/codegen-policy-diag.stderr"
  cmp "$work/codegen-policy-on.txt" "$work/codegen-policy-diag.txt"
 fi
fi
{ git -C "$root" rev-parse HEAD; git -C "$work/mesa" diff --cached | sha256sum; cc --version; rustc --version; meson --version; } > "$work/environment.txt"
meson introspect "$work/build" --buildoptions > "$work/buildoptions.json"
sha256sum "$work/build/src/nouveau/vulkan/libvulkan_nouveau.so" > "$work/library.sha256"
echo 'CPU/compiler checks completed. Hardware validation NOT RUN.'
