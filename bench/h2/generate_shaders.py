#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
shaders={'fullscreen.vert':'''#version 450
void main(){vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexIndex],0,1);}
'''}
for n in (1,4,7,8,16,32):
 for dynamic in (False,True):
  body=['#version 450','layout(location=0) out uint result;',
        'layout(set=0,binding=0,std140) uniform UBO {uvec4 data[64];} u;',
        'void main(){uint r=0u;uint base=uint(gl_FragCoord.x)&15u;']
  body += [f'r=r*1664525u+u.data[{"base+" if dynamic else ""}{i}].x;' for i in range(n)]
  shaders[f'ubo-{n}-{"dynamic" if dynamic else "static"}.frag']='\n'.join(body+['result=r;}'])
for name,source in shaders.items():
 p=out/name;p.write_text(source)
 subprocess.run(['glslangValidator','-V','--target-env','vulkan1.2','-o',str(p)+'.spv',str(p)],check=True)
 subprocess.run(['spirv-val','--target-env','vulkan1.2',str(p)+'.spv'],check=True)
