SECTION "Expanded dialog lookup", ROMX[$4000], BANK[$7F]
Lookup:
    ld a,[$C173]
    ld e,a
    ld a,[$C112]
    ld d,a
    cp 2
    jr c,.native
    jr nz,.extended
    ld a,e
    cp $B0
    jr c,.native
.extended:
    ld a,e
    sub $B0
    ld e,a
    ld a,d
    sbc 2
    ld d,a
    and a
    jr nz,.blank
    sla e
    rl d
    ld hl,$4200
    add hl,de
    ld de,$4110
    ld a,$7F
    ret
.blank:
    ld hl,$4112
    ld de,$4110
    ld a,$7F
    ret
.native:
    ld hl,$4741
    add hl,de
    push hl
    sla e
    rl d
    ld hl,$4001
    add hl,de
    pop de
    ld a,$1C
    ret
SECTION "Expanded dialog flag lookup", ROMX[$4060], BANK[$7F]
    call Lookup
    ld h,d
    ld l,e
    ret
