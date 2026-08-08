BITS 64
global pure_memset
pure_memset:
mov rcx,rdx
mov al,sil
rep stosb
ret
