BITS 64
global pure_mul
pure_mul:
mov rax,rdi
imul rax,rsi
ret
