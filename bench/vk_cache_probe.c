/* SPDX-License-Identifier: MIT
 * GM107 command-cache spike/recovery probe. Requires a real GTX 750 Ti.
 * Reports CPU recording/reset/wait times and driver-reported heap usage.
 * These are NOT FPS, GPU timestamps, or input-to-display latency.
 */
#define _POSIX_C_SOURCE 200809L
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define CHECK_VK(call) do { VkResult r = (call); if (r != VK_SUCCESS) { \
  fprintf(stderr, "%s failed: %d\n", #call, r); exit(1); } } while (0)
#define BLOCK_BYTES 65536u
#define BLOCKS 512u
#define TOTAL_BYTES ((VkDeviceSize)BLOCK_BYTES * BLOCKS)

static VkDevice device;
static VkPhysicalDevice physical;
static VkPhysicalDeviceMemoryProperties memprops;
static int has_budget;

static double now_ms(void)
{
   struct timespec t;
   clock_gettime(CLOCK_MONOTONIC, &t);
   return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}

static void make_buffer(VkBufferUsageFlags usage, VkMemoryPropertyFlags required,
                        VkMemoryPropertyFlags preferred, VkBuffer *buffer,
                        VkDeviceMemory *memory)
{
   VkBufferCreateInfo bi = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
      .size = TOTAL_BYTES, .usage = usage, .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
   CHECK_VK(vkCreateBuffer(device, &bi, NULL, buffer));
   VkMemoryRequirements req;
   vkGetBufferMemoryRequirements(device, *buffer, &req);
   uint32_t type = UINT32_MAX;
   for (unsigned pass = 0; pass < 2 && type == UINT32_MAX; pass++) {
      VkMemoryPropertyFlags flags = required | (pass == 0 ? preferred : 0);
      for (uint32_t i = 0; i < memprops.memoryTypeCount; i++) {
         if ((req.memoryTypeBits & (1u << i)) &&
             (memprops.memoryTypes[i].propertyFlags & flags) == flags) {
            type = i;
            break;
         }
      }
   }
   if (type == UINT32_MAX) { fprintf(stderr, "No compatible memory type\n"); exit(1); }
   VkMemoryAllocateInfo ai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
      .allocationSize = req.size, .memoryTypeIndex = type };
   CHECK_VK(vkAllocateMemory(device, &ai, NULL, memory));
   CHECK_VK(vkBindBufferMemory(device, *buffer, *memory, 0));
}

static void sample(unsigned round, const char *phase, double record,
                   double wait, double reset)
{
   VkPhysicalDeviceMemoryBudgetPropertiesEXT b = {
      .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_BUDGET_PROPERTIES_EXT };
   VkPhysicalDeviceMemoryProperties2 p = {
      .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_PROPERTIES_2,
      .pNext = has_budget ? &b : NULL };
   vkGetPhysicalDeviceMemoryProperties2(physical, &p);
   uint64_t usage = 0, budget = 0;
   for (uint32_t i = 0; i < p.memoryProperties.memoryHeapCount; i++) {
      if (p.memoryProperties.memoryHeaps[i].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) {
         usage += b.heapUsage[i]; budget += b.heapBudget[i];
      }
   }
   printf("%u,%s,%.6f,%.6f,%.6f,", round, phase, record, wait, reset);
   if (has_budget) printf("%llu,%llu\n", (unsigned long long)usage,
                          (unsigned long long)budget);
   else printf("NA,NA\n");
   fflush(stdout);
}

int main(void)
{
   VkApplicationInfo app = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
      .pApplicationName = "GM107 cache spike probe", .apiVersion = VK_API_VERSION_1_2 };
   VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
      .pApplicationInfo = &app };
   VkInstance instance;
   VkResult ir = vkCreateInstance(&ici, NULL, &instance);
   if (ir != VK_SUCCESS) { fprintf(stderr, "SKIP: no usable Vulkan ICD (%d)\n", ir); return 77; }
   uint32_t count = 0;
   CHECK_VK(vkEnumeratePhysicalDevices(instance, &count, NULL));
   VkPhysicalDevice *devices = calloc(count ? count : 1, sizeof(*devices));
   if (!devices) return 1;
   CHECK_VK(vkEnumeratePhysicalDevices(instance, &count, devices));
   VkPhysicalDeviceProperties props = {0};
   for (uint32_t i = 0; i < count; i++) {
      vkGetPhysicalDeviceProperties(devices[i], &props);
      if (props.vendorID == 0x10de && props.deviceID == 0x1380) {
         physical = devices[i]; break;
      }
   }
   free(devices);
   if (!physical) {
      fprintf(stderr, "SKIP: GTX 750 Ti (10de:1380) not found; no substitute GPU used\n");
      vkDestroyInstance(instance, NULL); return 77;
   }
   VkPhysicalDeviceDriverProperties driver = {
      .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES };
   VkPhysicalDeviceProperties2 props2 = {
      .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &driver };
   vkGetPhysicalDeviceProperties2(physical, &props2);
   fprintf(stderr, "GPU=%s driver=%s info=%s\n", props.deviceName,
           driver.driverName, driver.driverInfo);
   vkGetPhysicalDeviceMemoryProperties(physical, &memprops);
   uint32_t qcount = 0;
   vkGetPhysicalDeviceQueueFamilyProperties(physical, &qcount, NULL);
   VkQueueFamilyProperties *qp = calloc(qcount ? qcount : 1, sizeof(*qp));
   if (!qp) return 1;
   vkGetPhysicalDeviceQueueFamilyProperties(physical, &qcount, qp);
   uint32_t family = UINT32_MAX;
   for (uint32_t i = 0; i < qcount; i++) {
      if (qp[i].queueCount && (qp[i].queueFlags & VK_QUEUE_GRAPHICS_BIT)) { family = i; break; }
   }
   free(qp);
   if (family == UINT32_MAX) return 1;
   uint32_t ec = 0;
   CHECK_VK(vkEnumerateDeviceExtensionProperties(physical, NULL, &ec, NULL));
   VkExtensionProperties *ep = calloc(ec ? ec : 1, sizeof(*ep));
   if (!ep) return 1;
   CHECK_VK(vkEnumerateDeviceExtensionProperties(physical, NULL, &ec, ep));
   for (uint32_t i = 0; i < ec; i++)
      if (!strcmp(ep[i].extensionName, VK_EXT_MEMORY_BUDGET_EXTENSION_NAME)) has_budget = 1;
   free(ep);
   const char *ext = VK_EXT_MEMORY_BUDGET_EXTENSION_NAME;
   float priority = 1.0f;
   VkDeviceQueueCreateInfo qi = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
      .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &priority };
   VkDeviceCreateInfo di = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
      .queueCreateInfoCount = 1, .pQueueCreateInfos = &qi,
      .enabledExtensionCount = has_budget ? 1u : 0u,
      .ppEnabledExtensionNames = has_budget ? &ext : NULL };
   CHECK_VK(vkCreateDevice(physical, &di, NULL, &device));
   VkQueue queue;
   vkGetDeviceQueue(device, family, 0, &queue);
   VkBuffer dst, readback;
   VkDeviceMemory dstmem, readmem;
   make_buffer(VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT,
               0, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, &dst, &dstmem);
   make_buffer(VK_BUFFER_USAGE_TRANSFER_DST_BIT, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT,
               VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, &readback, &readmem);
   void *mapped;
   CHECK_VK(vkMapMemory(device, readmem, 0, VK_WHOLE_SIZE, 0, &mapped));
   VkCommandPool pool;
   VkCommandPoolCreateInfo pi = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
      .queueFamilyIndex = family };
   CHECK_VK(vkCreateCommandPool(device, &pi, NULL, &pool));
   VkCommandBuffer cmd;
   VkCommandBufferAllocateInfo cai = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
      .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1 };
   CHECK_VK(vkAllocateCommandBuffers(device, &cai, &cmd));
   VkFence fence;
   VkFenceCreateInfo fi = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO };
   CHECK_VK(vkCreateFence(device, &fi, NULL, &fence));
   uint32_t payload[BLOCK_BYTES / 4];
   puts("round,phase,record_ms,submit_wait_ms,reset_ms,local_heap_usage_bytes,local_heap_budget_bytes");
   sample(0, "initial", 0, 0, 0);
   for (unsigned round = 0; round < 8; round++) {
      for (unsigned i = 0; i < BLOCK_BYTES / 4; i++) payload[i] = 0x9e3779b9u ^ i ^ round;
      VkCommandBufferBeginInfo bi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
         .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT };
      double t0 = now_ms();
      CHECK_VK(vkBeginCommandBuffer(cmd, &bi));
      unsigned updates = round == 0 ? BLOCKS : 4;
      for (unsigned i = 0; i < updates; i++)
         vkCmdUpdateBuffer(cmd, dst, (VkDeviceSize)i * BLOCK_BYTES, BLOCK_BYTES, payload);
      VkMemoryBarrier mb = { .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
         .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT, .dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT };
      vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                           0, 1, &mb, 0, NULL, 0, NULL);
      VkBufferCopy copy = { .size = TOTAL_BYTES };
      vkCmdCopyBuffer(cmd, dst, readback, 1, &copy);
      mb.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
      vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                           0, 1, &mb, 0, NULL, 0, NULL);
      CHECK_VK(vkEndCommandBuffer(cmd));
      double t1 = now_ms();
      VkSubmitInfo si = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
         .commandBufferCount = 1, .pCommandBuffers = &cmd };
      CHECK_VK(vkQueueSubmit(queue, 1, &si, fence));
      CHECK_VK(vkWaitForFences(device, 1, &fence, VK_TRUE, 10000000000ull));
      double t2 = now_ms();
      VkMappedMemoryRange mr = { .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,
         .memory = readmem, .size = VK_WHOLE_SIZE };
      CHECK_VK(vkInvalidateMappedMemoryRanges(device, 1, &mr));
      const uint32_t *words = mapped;
      for (unsigned i = 0; i < TOTAL_BYTES / 4; i++) {
         unsigned expected_round = i < 4 * (BLOCK_BYTES / 4) ? round : 0;
         if (words[i] != (0x9e3779b9u ^ (i % (BLOCK_BYTES / 4)) ^ expected_round)) {
            fprintf(stderr, "FAIL: readback mismatch round=%u word=%u\n", round, i); return 1;
         }
      }
      sample(round, "before_reset", t1-t0, t2-t1, 0);
      double r0 = now_ms();
      CHECK_VK(vkResetCommandPool(device, pool, 0));
      double r1 = now_ms();
      sample(round, "after_reset", t1-t0, t2-t1, r1-r0);
      CHECK_VK(vkResetFences(device, 1, &fence));
   }
   vkTrimCommandPool(device, pool, 0);
   sample(8, "after_trim", 0, 0, 0);
   vkDestroyFence(device, fence, NULL);
   vkDestroyCommandPool(device, pool, NULL);
   vkUnmapMemory(device, readmem);
   vkDestroyBuffer(device, readback, NULL); vkFreeMemory(device, readmem, NULL);
   vkDestroyBuffer(device, dst, NULL); vkFreeMemory(device, dstmem, NULL);
   vkDestroyDevice(device, NULL); vkDestroyInstance(instance, NULL);
   fprintf(stderr, "PASS: all eight submissions and complete readbacks verified\n");
   return 0;
}