/* SPDX-License-Identifier: MIT */
#include "clb097.h"
#include "nir_builder.h"
#include "nir_serialize.h"
#include "nvk_descriptor_set_layout.h"
#include "nvk_device.h"
#include "nvk_instance.h"
#include "nvk_physical_device.h"
#include "nvk_shader.h"
#include "util/blob.h"
#include "vk_alloc.h"
#include "vk_pipeline.h"
#include <stdio.h>
#define CHECK(x)                                                                                   \
   do {                                                                                            \
      if (!(x)) {                                                                                  \
         fprintf(stderr, "FAIL %d: %s\n", __LINE__, #x);                                           \
         abort();                                                                                  \
      }                                                                                            \
   } while (0)
struct fixture {
   struct nvk_instance instance;
   struct nvk_physical_device pdev;
   struct nvk_device dev;
   struct nvk_descriptor_set_layout *layout;
   struct vk_pipeline_robustness_state rs;
};
struct options {
   unsigned loads, ordinary, dynamic, offset, index;
   bool dynamic_offset, dynamic_index, mixed, mutable, push;
   mesa_shader_stage stage;
};
static nir_shader *make_shader(struct fixture *f, struct options o) {
   unsigned bindings = o.ordinary + o.dynamic;
   free(f->layout);
   f->layout = calloc(1, sizeof(*f->layout) + bindings * sizeof(f->layout->binding[0]));
   CHECK(f->layout);
   f->layout->binding_count = bindings;
   f->layout->vk.dynamic_descriptor_count = o.dynamic;
   if (o.push)
      f->layout->flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR;
   nir_builder b = nir_builder_init_simple_shader(o.stage, nak_nir_options(f->pdev.nak), "h2-test");
   nir_address_format fmt = nvk_ubo_addr_format(&f->pdev, &f->rs);
   const struct glsl_type *array = glsl_array_type(glsl_uint_type(), 8192, 16);
   nir_def *sum = nir_imm_int(&b, 0);
   for (unsigned n = 0; n < bindings; n++) {
      bool dyn = n >= o.ordinary;
      f->layout->binding[n] = (struct nvk_descriptor_set_binding_layout){
          .type = dyn         ? VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC
                  : o.mutable ? VK_DESCRIPTOR_TYPE_MUTABLE_EXT
                              : VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
          .array_size = 2,
          .stride = 16,
          .offset = n * 32,
          .dynamic_buffer_index = dyn ? n - o.ordinary : 0};
      nir_def *idx = o.dynamic_index ? nir_load_subgroup_invocation(&b) : nir_imm_int(&b, o.index);
      nir_def *resource = nir_vulkan_resource_index(
          &b, nir_address_format_num_components(fmt), nir_address_format_bit_size(fmt), idx,
          .desc_set = 0, .binding = n, .desc_type = nir_descriptor_type_uniform_buffer,
          .resource_type = nir_resource_type_uniform_buffer);
      nir_def *addr = nir_load_vulkan_descriptor(&b, nir_address_format_num_components(fmt),
                                                 nir_address_format_bit_size(fmt), resource,
                                                 .desc_type = nir_descriptor_type_uniform_buffer);
      nir_deref_instr *base =
          nir_build_deref_cast_with_alignment(&b, addr, nir_var_mem_ubo, array, 0, 16, 0);
      for (unsigned i = 0; i < o.loads; i++) {
         nir_def *element = (o.dynamic_offset || (o.mixed && i == 0))
                                ? nir_load_subgroup_invocation(&b)
                                : nir_imm_int(&b, o.offset / 16 + i);
         sum = nir_iadd(&b, sum, nir_load_deref(&b, nir_build_deref_array(&b, base, element)));
      }
   }
   if (o.stage == MESA_SHADER_COMPUTE) {
      b.shader->info.shared_size = 4;
      nir_store_shared(&b, sum, nir_imm_int(&b, 0), .align_mul = 4);
   } else
      nir_store_output(&b, sum, nir_imm_int(&b, 0), .write_mask = 1, .src_type = nir_type_uint32,
                       .io_semantics = {.location = o.stage == MESA_SHADER_FRAGMENT
                                                        ? FRAG_RESULT_DATA0
                                                        : VARYING_SLOT_VAR0,
                                        .num_slots = 1});
   nir_validate_shader(b.shader, "fixture");
   return b.shader;
}


int main(void) {
   glsl_type_singleton_init_or_ref();
   struct fixture f = {0};
   f.pdev.info=(struct nv_device_info){.chipset=0x117,.sm=50,.cls_eng3d=MAXWELL_A,.max_warps_per_mp=64};
   /* Bit 11 is the pinned H2 patch ABI; used only in h2/h2-h3 CPU jobs. */
   if (getenv("GM107_PROBE_H2")) f.pdev.debug_flags = 1u << 11;
   f.pdev.vk.instance=&f.instance.vk;
   f.pdev.nak=nak_compiler_create(&f.pdev.info); CHECK(f.pdev.nak);
   f.dev.vk.physical=&f.pdev.vk; f.dev.vk.alloc=*vk_default_allocator();
   f.dev.vk.base.type=VK_OBJECT_TYPE_DEVICE;
   f.rs=(struct vk_pipeline_robustness_state){
      .uniform_buffers=VK_PIPELINE_ROBUSTNESS_BUFFER_BEHAVIOR_ROBUST_BUFFER_ACCESS_EXT,
      .storage_buffers=VK_PIPELINE_ROBUSTNESS_BUFFER_BEHAVIOR_ROBUST_BUFFER_ACCESS_EXT,
      .images=VK_PIPELINE_ROBUSTNESS_IMAGE_BEHAVIOR_ROBUST_IMAGE_ACCESS_2_EXT};
   for (unsigned stage=0;stage<3;stage++) for(unsigned dynamic=0;dynamic<2;dynamic++) {
      struct options o={.loads=8,.ordinary=1,.dynamic_offset=dynamic,
         .stage=stage==0?MESA_SHADER_FRAGMENT:stage==1?MESA_SHADER_VERTEX:MESA_SHADER_COMPUTE};
      nir_shader *nir=make_shader(&f,o);
      nvk_device_shader_ops.preprocess_nir(&f.pdev.vk,nir,&f.rs);
      struct vk_descriptor_set_layout *layouts[]={&f.layout->vk};
      struct vk_shader_compile_info info={.stage=o.stage,.nir=nir,.robustness=&f.rs,
         .flags=VK_SHADER_CREATE_NO_TASK_SHADER_BIT_EXT,.set_layout_count=1,.set_layouts=layouts};
      struct vk_shader *out;
      CHECK(nvk_device_shader_ops.compile(&f.dev.vk,1,&info,NULL,NULL,NULL,&out)==VK_SUCCESS);
      struct nvk_shader *sh=container_of(out,struct nvk_shader,vk);
      printf("case %u %u: %u instr %u GPR %u bytes ",stage,dynamic,
             sh->info.num_instrs,sh->info.num_gprs,sh->code_size);
      for(unsigned i=0;i<sh->code_size;i++) printf("%02x",((const unsigned char *)sh->code_ptr)[i]);
      puts("");
      sh->vk.ops->destroy(&f.dev.vk,&sh->vk,NULL);
   }
   free(f.layout); nak_compiler_destroy(f.pdev.nak); glsl_type_singleton_decref();
}
