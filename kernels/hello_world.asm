BITS 64
section .text
global _start
_start:
mov rax,0x1
mov rdi,0x1
lea rsi,[rel msg]
mov rdx,0xd
syscall
mov rax,0x3c
xor rdi,rdi
syscall
section .rodata
msg db 'Hello, World',0xa
