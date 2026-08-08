BITS 64
global pure_memcpy
pure_memcpy:
mov rcx,rdx
rep movsb
ret
