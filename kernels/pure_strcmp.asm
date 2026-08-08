BITS 64
global pure_strcmp
pure_strcmp:
xor rax,rax
.Lcmp:
mov cl,[rdi]
mov dl,[rsi]
cmp cl,dl
jne .Ldiff
test cl,cl
jz .Lend
inc rdi
inc rsi
jmp .Lcmp
.Ldiff:
sbb rax,rax
or rax,1
.Lend:
ret
