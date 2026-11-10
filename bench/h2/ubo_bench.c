/* SPDX-License-Identifier: MIT
 * Offscreen graphics UBO timing + exhaustive integer pixel verification.
 * --software is explicitly harness-only; no implicit fallback to another GPU.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <vulkan/vulkan.h>
#define CHECK(x)                                                                                   \
   do {                                                                                            \
      if (!(x)) {                                                                                  \
         fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x);                                      \
         exit(1);                                                                                  \
      }                                                                                            \
   } while (0)
#define VK(x)                                                                                      \
   do {                                                                                            \
      VkResult r_ = (x);                                                                           \
      if (r_ != VK_SUCCESS) {                                                                      \
         fprintf(stderr, "FAIL %s: %d\n", #x, r_);                                                 \
         exit(1);                                                                                  \
      }                                                                                            \
   } while (0)
static VkDevice dev;
static VkPhysicalDeviceMemoryProperties mem;
static unsigned width = 1280, height = 720, reads = 8, draws = 1, samples = 30, warmup = 5, errors;
static bool dynamic, rebind, software, validation, push, robust2, null_ubo, oob, switch_pipeline;
static double now(void) {
   struct timespec t;
   CHECK(!clock_gettime(CLOCK_MONOTONIC, &t));
   return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}
static VKAPI_ATTR VkBool32 VKAPI_CALL message(VkDebugUtilsMessageSeverityFlagBitsEXT s,
                                              VkDebugUtilsMessageTypeFlagsEXT t,
                                              const VkDebugUtilsMessengerCallbackDataEXT *d,
                                              void *u) {
   (void)t;
   (void)u;
   if (s & VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT)
      errors++;
   fprintf(stderr, "VALIDATION %s\n", d->pMessage);
   return VK_FALSE;
}
static unsigned type(uint32_t bits, VkMemoryPropertyFlags flags) {
   for (unsigned i = 0; i < mem.memoryTypeCount; i++)
      if ((bits & (1u << i)) && (mem.memoryTypes[i].propertyFlags & flags) == flags)
         return i;
   CHECK(false);
   return 0;
}
struct buffer {
   VkBuffer b;
   VkDeviceMemory m;
   void *ptr;
   bool coherent;
};
static struct buffer buffer(VkDeviceSize size, VkBufferUsageFlags usage) {
   struct buffer b = {0};
   VkBufferCreateInfo ci = {
       .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = size, .usage = usage};
   VK(vkCreateBuffer(dev, &ci, NULL, &b.b));
   VkMemoryRequirements req;
   vkGetBufferMemoryRequirements(dev, b.b, &req);
   unsigned mt = type(req.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT);
   fprintf(stderr, "BUFFER size=%llu memory_type=%u flags=%u\n", (unsigned long long)size, mt,
           mem.memoryTypes[mt].propertyFlags);
   VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                              .allocationSize = req.size,
                              .memoryTypeIndex = mt};
   VK(vkAllocateMemory(dev, &ai, NULL, &b.m));
   VK(vkBindBufferMemory(dev, b.b, b.m, 0));
   VK(vkMapMemory(dev, b.m, 0, VK_WHOLE_SIZE, 0, &b.ptr));
   b.coherent = mem.memoryTypes[mt].propertyFlags & VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
   return b;
}
static void syncbuf(struct buffer b, bool flush) {
   if (b.coherent)
      return;
   VkMappedMemoryRange r = {
       .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE, .memory = b.m, .size = VK_WHOLE_SIZE};
   if (flush)
      VK(vkFlushMappedMemoryRanges(dev, 1, &r));
   else
      VK(vkInvalidateMappedMemoryRanges(dev, 1, &r));
}
static void freebuf(struct buffer b) {
   vkUnmapMemory(dev, b.m);
   vkDestroyBuffer(dev, b.b, NULL);
   vkFreeMemory(dev, b.m, NULL);
}
static VkShaderModule shader(const char *dir, const char *name) {
   char path[4096];
   CHECK(snprintf(path, sizeof(path), "%s/%s", dir, name) < (int)sizeof(path));
   FILE *f = fopen(path, "rb");
   CHECK(f);
   CHECK(!fseek(f, 0, SEEK_END));
   long n = ftell(f);
   CHECK(n > 0 && n % 4 == 0);
   rewind(f);
   uint32_t *data = malloc(n);
   CHECK(data && fread(data, 1, n, f) == (size_t)n);
   fclose(f);
   VkShaderModuleCreateInfo ci = {
       .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, .codeSize = n, .pCode = data};
   VkShaderModule m;
   VK(vkCreateShaderModule(dev, &ci, NULL, &m));
   free(data);
   return m;
}
static unsigned number(const char *s) {
   char *end;
   unsigned long n = strtoul(s, &end, 10);
   CHECK(*s && !*end && n <= 100000);
   return n;
}
static uint32_t value(unsigned iteration, unsigned binding, unsigned element) {
   return UINT32_C(0x9e3779b9) * (iteration + 1) + UINT32_C(0x85ebca6b) * binding + element * 17u;
}
int main(int argc, char **argv) {
   const char *dir = NULL;
   for (int i = 1; i < argc; i++) {
      if (!strcmp(argv[i], "--software"))
         software = true;
      else if (!strcmp(argv[i], "--push"))
         push = true;
      else if (!strcmp(argv[i], "--switch"))
         switch_pipeline = true;
      else if (!strcmp(argv[i], "--robust2"))
         robust2 = true;
      else if (!strcmp(argv[i], "--null")) {
         null_ubo = true;
         robust2 = true;
      } else if (!strcmp(argv[i], "--null-only"))
         null_ubo = true;
      else if (!strcmp(argv[i], "--oob")) {
         oob = true;
         robust2 = true;
      } else if (!strcmp(argv[i], "--dynamic"))
         dynamic = true;
      else if (!strcmp(argv[i], "--rebind"))
         rebind = true;
      else if (!strcmp(argv[i], "--validation"))
         validation = true;
      else if (!strcmp(argv[i], "--shaders") && i + 1 < argc)
         dir = argv[++i];
#define ARG(name, var) else if (!strcmp(argv[i], name) && i + 1 < argc) var = number(argv[++i])
      ARG("--width", width);
      ARG("--height", height);
      ARG("--reads", reads);
      ARG("--draws", draws);
      ARG("--samples", samples);
      ARG("--warmup", warmup);
      else {
         fprintf(stderr, "Usage: --shaders DIR [--reads 1|4|7|8|16|32 --width N --height N --draws "
                         "N --samples N --warmup N --rebind --dynamic --push --switch --robust2 "
                         "--null --null-only --oob --validation --software]\n");
         return 2;
      }
   }
   CHECK(dir && width && height && width <= 4096 && height <= 4096 && draws && draws <= width &&
         samples && samples <= 10000 && warmup <= 1000);
   CHECK(reads == 1 || reads == 4 || reads == 7 || reads == 8 || reads == 16 || reads == 32);
   VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                            .pApplicationName = "H2 UBO",
                            .apiVersion = VK_API_VERSION_1_2};
   const char *layer = "VK_LAYER_KHRONOS_validation", *ext = VK_EXT_DEBUG_UTILS_EXTENSION_NAME;
   VkDebugUtilsMessengerCreateInfoEXT dbg = {
       .sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
       .messageSeverity = VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT |
                          VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT,
       .messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT |
                      VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT |
                      VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT,
       .pfnUserCallback = message};
   VkInstanceCreateInfo ici = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                               .pApplicationInfo = &app,
                               .enabledLayerCount = validation,
                               .ppEnabledLayerNames = &layer,
                               .enabledExtensionCount = validation,
                               .ppEnabledExtensionNames = &ext,
                               .pNext = validation ? &dbg : NULL};
   VkInstance instance;
   VkResult ir = vkCreateInstance(&ici, NULL, &instance);
   if (ir != VK_SUCCESS) {
      fprintf(stderr, "SKIP instance/layer/ICD unavailable: %d\n", ir);
      return 77;
   }
   VkDebugUtilsMessengerEXT messenger = VK_NULL_HANDLE;
   if (validation) {
      PFN_vkCreateDebugUtilsMessengerEXT fn =
          (PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(
              instance, "vkCreateDebugUtilsMessengerEXT");
      CHECK(fn);
      VK(fn(instance, &dbg, NULL, &messenger));
   }
   uint32_t count = 0;
   VK(vkEnumeratePhysicalDevices(instance, &count, NULL));
   VkPhysicalDevice *gpus = calloc(count ? count : 1, sizeof(*gpus));
   CHECK(gpus);
   VK(vkEnumeratePhysicalDevices(instance, &count, gpus));
   VkPhysicalDevice gpu = VK_NULL_HANDLE;
   VkPhysicalDeviceProperties props = {0};
   for (unsigned i = 0; i < count; i++) {
      vkGetPhysicalDeviceProperties(gpus[i], &props);
      if (software ? props.deviceType == VK_PHYSICAL_DEVICE_TYPE_CPU
                   : props.vendorID == 0x10de && props.deviceID == 0x1380) {
         gpu = gpus[i];
         break;
      }
   }
   free(gpus);
   if (!gpu) {
      fprintf(stderr, "SKIP requested GPU not found; no substitute\n");
      return 77;
   }
   VkPhysicalDeviceDriverProperties driver = {
       .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
   VkPhysicalDeviceProperties2 p2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,
                                     .pNext = &driver};
   vkGetPhysicalDeviceProperties2(gpu, &p2);
   fprintf(stderr, "DEVICE %s driver=%s info=%s software=%u\n", props.deviceName, driver.driverName,
           driver.driverInfo, software);
   fprintf(stderr, "PIPELINE_CACHE_UUID ");
   for (unsigned i = 0; i < VK_UUID_SIZE; i++)
      fprintf(stderr, "%02x", props.pipelineCacheUUID[i]);
   fprintf(stderr,
           "\nCONFIG reads=%u draws=%u rebind=%u dynamic=%u width=%u height=%u validation=%u\n",
           reads, draws, rebind, dynamic, width, height, validation);
   vkGetPhysicalDeviceMemoryProperties(gpu, &mem);
   VkFormatProperties fp;
   vkGetPhysicalDeviceFormatProperties(gpu, VK_FORMAT_R32_UINT, &fp);
   CHECK((fp.optimalTilingFeatures &
          (VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT | VK_FORMAT_FEATURE_TRANSFER_SRC_BIT)) ==
         (VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT | VK_FORMAT_FEATURE_TRANSFER_SRC_BIT));
   uint32_t nq = 0;
   vkGetPhysicalDeviceQueueFamilyProperties(gpu, &nq, NULL);
   VkQueueFamilyProperties *qp = calloc(nq, sizeof(*qp));
   CHECK(qp);
   vkGetPhysicalDeviceQueueFamilyProperties(gpu, &nq, qp);
   unsigned family = UINT32_MAX, bits = 0;
   for (unsigned i = 0; i < nq; i++)
      if (qp[i].queueCount && (qp[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) &&
          qp[i].timestampValidBits) {
         family = i;
         bits = qp[i].timestampValidBits;
         break;
      }
   free(qp);
   CHECK(family != UINT32_MAX && bits <= 64 && props.limits.timestampPeriod > 0);
   float priority = 1;
   VkDeviceQueueCreateInfo qi = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
                                 .queueFamilyIndex = family,
                                 .queueCount = 1,
                                 .pQueuePriorities = &priority};
   VkPhysicalDeviceFeatures supported;
   vkGetPhysicalDeviceFeatures(gpu, &supported);
   VkPhysicalDeviceFeatures enabled = {.robustBufferAccess = supported.robustBufferAccess};
   const char *extensions[2];
   unsigned ne = 0;
   if (push)
      extensions[ne++] = VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME;
   if (robust2 || null_ubo)
      extensions[ne++] = VK_EXT_ROBUSTNESS_2_EXTENSION_NAME;
   VkPhysicalDeviceRobustness2FeaturesEXT rf = {
       .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ROBUSTNESS_2_FEATURES_EXT};
   if (robust2 || null_ubo) {
      VkPhysicalDeviceFeatures2 f2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
                                      .pNext = &rf};
      vkGetPhysicalDeviceFeatures2(gpu, &f2);
      CHECK(!robust2 || rf.robustBufferAccess2);
      CHECK(!null_ubo || rf.nullDescriptor);
      rf.robustBufferAccess2 = robust2;
      rf.nullDescriptor = null_ubo;
      rf.robustImageAccess2 = false;
   }
   fprintf(stderr, "EXTRA push=%u robust2=%u null=%u oob=%u switch=%u\n", push, robust2, null_ubo,
           oob, switch_pipeline);
   VkDeviceCreateInfo dci = {.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
                             .queueCreateInfoCount = 1,
                             .pQueueCreateInfos = &qi,
                             .pEnabledFeatures = &enabled,
                             .enabledExtensionCount = ne,
                             .ppEnabledExtensionNames = extensions,
                             .pNext = (robust2 || null_ubo) ? &rf : NULL};
   VK(vkCreateDevice(gpu, &dci, NULL, &dev));
   VkQueue queue;
   vkGetDeviceQueue(dev, family, 0, &queue);
   PFN_vkCmdPushDescriptorSetKHR cmd_push =
       (PFN_vkCmdPushDescriptorSetKHR)vkGetDeviceProcAddr(dev, "vkCmdPushDescriptorSetKHR");
   CHECK(!push || cmd_push);
   FILE *maps = fopen("/proc/self/maps", "r");
   if (maps) {
      char line[8192];
      while (fgets(line, sizeof(line), maps))
         if (strstr(line, "libvulkan_nouveau") || strstr(line, "libvulkan_lvp") ||
             strstr(line, "libGLX_nvidia"))
            fprintf(stderr, "MAPPING %s", line);
      fclose(maps);
   }
   unsigned bindings = rebind ? draws : 1;
   VkDeviceSize align = props.limits.minUniformBufferOffsetAlignment,
                stride = (1024 + align - 1) / align * align;
   struct buffer ubo = buffer(stride * bindings, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT),
                 readback =
                     buffer((VkDeviceSize)width * height * 4, VK_BUFFER_USAGE_TRANSFER_DST_BIT);
   VkDescriptorSetLayoutBinding binding = {.binding = 0,
                                           .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                                           .descriptorCount = 1,
                                           .stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT};
   VkDescriptorSetLayoutCreateInfo slci = {
       .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
       .flags = push ? VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR : 0,
       .bindingCount = 1,
       .pBindings = &binding};
   VkDescriptorSetLayout sl;
   VK(vkCreateDescriptorSetLayout(dev, &slci, NULL, &sl));
   VkPipelineLayoutCreateInfo plci = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
                                      .setLayoutCount = 1,
                                      .pSetLayouts = &sl};
   VkPipelineLayout layout;
   VK(vkCreatePipelineLayout(dev, &plci, NULL, &layout));
   VkDescriptorPoolSize ps = {.type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                              .descriptorCount = bindings};
   VkDescriptorPoolCreateInfo dpci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
                                      .maxSets = bindings,
                                      .poolSizeCount = 1,
                                      .pPoolSizes = &ps};
   VkDescriptorPool pool;
   VK(vkCreateDescriptorPool(dev, &dpci, NULL, &pool));
   VkDescriptorSet *sets = calloc(bindings, sizeof(*sets));
   CHECK(sets);
   if (!push)
      for (unsigned i = 0; i < bindings; i++) {
         VkDescriptorSetAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
                                           .descriptorPool = pool,
                                           .descriptorSetCount = 1,
                                           .pSetLayouts = &sl};
         VK(vkAllocateDescriptorSets(dev, &ai, &sets[i]));
         VkDescriptorBufferInfo bi = {.buffer = null_ubo ? VK_NULL_HANDLE : ubo.b,
                                      .offset = null_ubo ? 0 : stride * i,
                                      .range = null_ubo ? VK_WHOLE_SIZE
                                               : oob    ? 256
                                                        : 1024};
         VkWriteDescriptorSet wr = {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
                                    .dstSet = sets[i],
                                    .dstBinding = 0,
                                    .descriptorCount = 1,
                                    .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                                    .pBufferInfo = &bi};
         vkUpdateDescriptorSets(dev, 1, &wr, 0, NULL);
      }
   VkImageCreateInfo imci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
                             .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R32_UINT,
                             .extent = {width, height, 1},
                             .mipLevels = 1,
                             .arrayLayers = 1,
                             .samples = VK_SAMPLE_COUNT_1_BIT,
                             .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
                                      VK_IMAGE_USAGE_TRANSFER_SRC_BIT};
   VkImage image;
   VK(vkCreateImage(dev, &imci, NULL, &image));
   VkMemoryRequirements req;
   vkGetImageMemoryRequirements(dev, image, &req);
   VkMemoryAllocateInfo mai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                               .allocationSize = req.size,
                               .memoryTypeIndex = type(req.memoryTypeBits, 0)};
   VkDeviceMemory image_mem;
   VK(vkAllocateMemory(dev, &mai, NULL, &image_mem));
   VK(vkBindImageMemory(dev, image, image_mem, 0));
   VkImageViewCreateInfo ivci = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
                                 .image = image,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D,
                                 .format = VK_FORMAT_R32_UINT,
                                 .subresourceRange = {.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                                                      .levelCount = 1,
                                                      .layerCount = 1}};
   VkImageView view;
   VK(vkCreateImageView(dev, &ivci, NULL, &view));
   VkAttachmentDescription attachment = {.format = VK_FORMAT_R32_UINT,
                                         .samples = VK_SAMPLE_COUNT_1_BIT,
                                         .loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR,
                                         .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
                                         .stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE,
                                         .stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE,
                                         .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED,
                                         .finalLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL};
   VkAttachmentReference ref = {.attachment = 0,
                                .layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
   VkSubpassDescription sub = {.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS,
                               .colorAttachmentCount = 1,
                               .pColorAttachments = &ref};
   VkSubpassDependency deps[2] = {{.srcSubpass = VK_SUBPASS_EXTERNAL,
                                   .dstSubpass = 0,
                                   .srcStageMask = VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                                   .dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                                   .dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT},
                                  {.srcSubpass = 0,
                                   .dstSubpass = VK_SUBPASS_EXTERNAL,
                                   .srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                                   .dstStageMask = VK_PIPELINE_STAGE_TRANSFER_BIT,
                                   .srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,
                                   .dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT}};
   VkRenderPassCreateInfo rpci = {.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,
                                  .attachmentCount = 1,
                                  .pAttachments = &attachment,
                                  .subpassCount = 1,
                                  .pSubpasses = &sub,
                                  .dependencyCount = 2,
                                  .pDependencies = deps};
   VkRenderPass rp;
   VK(vkCreateRenderPass(dev, &rpci, NULL, &rp));
   VkFramebufferCreateInfo fbci = {.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,
                                   .renderPass = rp,
                                   .attachmentCount = 1,
                                   .pAttachments = &view,
                                   .width = width,
                                   .height = height,
                                   .layers = 1};
   VkFramebuffer fb;
   VK(vkCreateFramebuffer(dev, &fbci, NULL, &fb));
   char name[100];
   snprintf(name, sizeof(name), "ubo-%u-%s.frag.spv", reads, dynamic ? "dynamic" : "static");
   VkShaderModule vs = shader(dir, "fullscreen.vert.spv"), fs = shader(dir, name);
   VkPipelineShaderStageCreateInfo stages[2] = {
       {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_VERTEX_BIT,
        .module = vs,
        .pName = "main"},
       {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        .stage = VK_SHADER_STAGE_FRAGMENT_BIT,
        .module = fs,
        .pName = "main"}};
   VkPipelineVertexInputStateCreateInfo vi = {
       .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
   VkPipelineInputAssemblyStateCreateInfo ia = {
       .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
       .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
   VkViewport vp = {.width = width, .height = height, .maxDepth = 1};
   VkPipelineViewportStateCreateInfo vps = {
       .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
       .viewportCount = 1,
       .pViewports = &vp,
       .scissorCount = 1};
   VkPipelineRasterizationStateCreateInfo raster = {
       .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
       .polygonMode = VK_POLYGON_MODE_FILL,
       .cullMode = VK_CULL_MODE_NONE,
       .frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE,
       .lineWidth = 1};
   VkPipelineMultisampleStateCreateInfo ms = {
       .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
       .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT};
   VkPipelineColorBlendAttachmentState ba = {.colorWriteMask = VK_COLOR_COMPONENT_R_BIT};
   VkPipelineColorBlendStateCreateInfo blend = {
       .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
       .attachmentCount = 1,
       .pAttachments = &ba};
   VkDynamicState scissor = VK_DYNAMIC_STATE_SCISSOR;
   VkPipelineDynamicStateCreateInfo ds = {.sType =
                                              VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
                                          .dynamicStateCount = 1,
                                          .pDynamicStates = &scissor};
   VkGraphicsPipelineCreateInfo pci = {.sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
                                       .stageCount = 2,
                                       .pStages = stages,
                                       .pVertexInputState = &vi,
                                       .pInputAssemblyState = &ia,
                                       .pViewportState = &vps,
                                       .pRasterizationState = &raster,
                                       .pMultisampleState = &ms,
                                       .pColorBlendState = &blend,
                                       .pDynamicState = &ds,
                                       .layout = layout,
                                       .renderPass = rp};
   VkPipeline pipeline;
   VK(vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &pci, NULL, &pipeline));
   VkPipeline second = VK_NULL_HANDLE;
   VkShaderModule alt_fs = VK_NULL_HANDLE;
   if (switch_pipeline) {
      snprintf(name, sizeof(name), "ubo-1-%s.frag.spv", dynamic ? "dynamic" : "static");
      alt_fs = shader(dir, name);
      stages[1].module = alt_fs;
      VK(vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &pci, NULL, &second));
      stages[1].module = fs;
   }
   VkCommandPoolCreateInfo cpci = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
                                   .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
                                   .queueFamilyIndex = family};
   VkCommandPool cp;
   VK(vkCreateCommandPool(dev, &cpci, NULL, &cp));
   VkCommandBufferAllocateInfo cai = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
                                      .commandPool = cp,
                                      .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                                      .commandBufferCount = 1};
   VkCommandBuffer cmd;
   VK(vkAllocateCommandBuffers(dev, &cai, &cmd));
   VkFenceCreateInfo fci = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
   VkFence fence;
   VK(vkCreateFence(dev, &fci, NULL, &fence));
   VkQueryPoolCreateInfo qci = {.sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
                                .queryType = VK_QUERY_TYPE_TIMESTAMP,
                                .queryCount = 2};
   VkQueryPool queries;
   VK(vkCreateQueryPool(dev, &qci, NULL, &queries));
   puts("sample,gpu_ms,cpu_record_ms,submit_wait_ms,readback_ok,software");
   for (unsigned it = 0; it < samples + warmup; it++) {
      for (unsigned b = 0; b < bindings; b++) {
         uint32_t *data = (uint32_t *)((char *)ubo.ptr + stride * b);
         for (unsigned e = 0; e < 64; e++)
            for (unsigned c = 0; c < 4; c++)
               data[e * 4 + c] = value(it, b, e);
      }
      syncbuf(ubo, true);
      double begin = now();
      VK(vkResetCommandBuffer(cmd, 0));
      VkCommandBufferBeginInfo cbi = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
                                      .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
      VK(vkBeginCommandBuffer(cmd, &cbi));
      vkCmdResetQueryPool(cmd, queries, 0, 2);
      vkCmdWriteTimestamp(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, queries, 0);
      VkClearValue clear = {.color.uint32 = {0, 0, 0, 0}};
      VkRenderPassBeginInfo rbi = {.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,
                                   .renderPass = rp,
                                   .framebuffer = fb,
                                   .renderArea.extent = {width, height},
                                   .clearValueCount = 1,
                                   .pClearValues = &clear};
      vkCmdBeginRenderPass(cmd, &rbi, VK_SUBPASS_CONTENTS_INLINE);
      vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);
      for (unsigned d = 0; d < draws; d++) {
         unsigned b = rebind ? d : 0;
         if (switch_pipeline)
            vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, d & 1 ? second : pipeline);
         if (!d || rebind) {
            if (push) {
               VkDescriptorBufferInfo bi = {.buffer = null_ubo ? VK_NULL_HANDLE : ubo.b,
                                            .offset = null_ubo ? 0 : stride * b,
                                            .range = null_ubo ? VK_WHOLE_SIZE
                                                     : oob    ? 256
                                                              : 1024};
               VkWriteDescriptorSet wr = {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
                                          .dstBinding = 0,
                                          .descriptorCount = 1,
                                          .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                                          .pBufferInfo = &bi};
               cmd_push(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, layout, 0, 1, &wr);
            } else
               vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, layout, 0, 1, &sets[b],
                                       0, NULL);
         }
         unsigned left = d * width / draws, right = (d + 1) * width / draws;
         VkRect2D rect = {.offset = {(int32_t)left, 0}, .extent = {right - left, height}};
         vkCmdSetScissor(cmd, 0, 1, &rect);
         vkCmdDraw(cmd, 3, 1, 0, 0);
      }
      vkCmdEndRenderPass(cmd);
      vkCmdWriteTimestamp(cmd, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, queries, 1);
      VkBufferImageCopy copy = {
          .imageSubresource = {.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT, .layerCount = 1},
          .imageExtent = {width, height, 1}};
      vkCmdCopyImageToBuffer(cmd, image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, readback.b, 1,
                             &copy);
      VkMemoryBarrier mb = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
                            .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
                            .dstAccessMask = VK_ACCESS_HOST_READ_BIT};
      vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1,
                           &mb, 0, NULL, 0, NULL);
      VK(vkEndCommandBuffer(cmd));
      double record = now() - begin;
      VkSubmitInfo submit = {
          .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cmd};
      begin = now();
      VK(vkQueueSubmit(queue, 1, &submit, fence));
      VK(vkWaitForFences(dev, 1, &fence, VK_TRUE, UINT64_C(30000000000)));
      double wait = now() - begin;
      VK(vkResetFences(dev, 1, &fence));
      uint64_t ts[4] = {0};
      VK(vkGetQueryPoolResults(dev, queries, 0, 2, sizeof(ts), ts, 16,
                               VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WITH_AVAILABILITY_BIT));
      CHECK(ts[1] && ts[3]);
      uint64_t mask = bits == 64 ? UINT64_MAX : (UINT64_C(1) << bits) - 1;
      double gpu_ms = ((ts[2] - ts[0]) & mask) * (double)props.limits.timestampPeriod / 1e6;
      syncbuf(readback, false);
      for (unsigned d = 0; d < draws; d++)
         for (unsigned x = d * width / draws; x < (d + 1) * width / draws; x++) {
            uint32_t want = 0;
            for (unsigned n = 0; n < (switch_pipeline && (d & 1) ? 1 : reads); n++) {
               unsigned e = n + (dynamic ? (x & 15) : 0);
               want = want * 1664525u +
                      ((null_ubo || (oob && e >= 16)) ? 0 : value(it, rebind ? d : 0, e));
            }
            for (unsigned y = 0; y < height; y++)
               CHECK(((uint32_t *)readback.ptr)[y * width + x] == want);
         }
      if (it >= warmup) {
         printf("%u,%.9f,%.6f,%.6f,1,%u\n", it - warmup, gpu_ms, record, wait, software);
         fflush(stdout);
      }
   }
   vkDestroyQueryPool(dev, queries, NULL);
   vkDestroyFence(dev, fence, NULL);
   vkDestroyCommandPool(dev, cp, NULL);
   vkDestroyPipeline(dev, pipeline, NULL);
   if (second)
      vkDestroyPipeline(dev, second, NULL);
   if (alt_fs)
      vkDestroyShaderModule(dev, alt_fs, NULL);
   vkDestroyShaderModule(dev, vs, NULL);
   vkDestroyShaderModule(dev, fs, NULL);
   vkDestroyFramebuffer(dev, fb, NULL);
   vkDestroyRenderPass(dev, rp, NULL);
   vkDestroyImageView(dev, view, NULL);
   vkDestroyImage(dev, image, NULL);
   vkFreeMemory(dev, image_mem, NULL);
   vkDestroyDescriptorPool(dev, pool, NULL);
   free(sets);
   vkDestroyPipelineLayout(dev, layout, NULL);
   vkDestroyDescriptorSetLayout(dev, sl, NULL);
   freebuf(ubo);
   freebuf(readback);
   vkDestroyDevice(dev, NULL);
   if (messenger) {
      PFN_vkDestroyDebugUtilsMessengerEXT fn =
          (PFN_vkDestroyDebugUtilsMessengerEXT)vkGetInstanceProcAddr(
              instance, "vkDestroyDebugUtilsMessengerEXT");
      fn(instance, messenger, NULL);
   }
   vkDestroyInstance(instance, NULL);
   CHECK(!errors);
   fprintf(stderr, "PASS all pixels, software=%u; no FPS claim\n", software);
   return 0;
}
