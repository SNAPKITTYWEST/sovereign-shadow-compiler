BITS 64
global pure_loop
pure_loop:
xor rax,rax
.L1:
inc rax
cmp rax,rdi
jl .L1
ret
