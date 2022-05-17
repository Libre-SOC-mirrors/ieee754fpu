; SPDX-License-Identifier: LGPL-2.1-or-later

; Test to see if using smt-lib2's floating-point support for checking fpu hw
; is feasible by implementing fp multiplication with bit-vectors and seeing if
; the smt checkers work. The idea is we can run this test before putting in
; all the effort to add support in yosys and nmigen for smtlib2 reals and
; floating-point numbers.

; run with: z3 -smt2 fp16mul_test.smt2

; create some handy type aliases
(define-sort bv1 () (_ BitVec 1))
(define-sort bv2 () (_ BitVec 2))
(define-sort bv4 () (_ BitVec 4))
(define-sort bv5 () (_ BitVec 5))
(define-sort bv8 () (_ BitVec 8))
(define-sort bv10 () (_ BitVec 10))
(define-sort bv11 () (_ BitVec 11))
(define-sort bv16 () (_ BitVec 16))
(define-sort bv22 () (_ BitVec 22))
(define-sort bv32 () (_ BitVec 32))

; type for signed f16 exponents
(define-sort f16_sexp_t () bv8)
; signed less-than comparison
(define-fun f16_sexp_lt ((a f16_sexp_t) (b f16_sexp_t)) Bool
    (bvult (bvxor #x80 a) (bvxor #x80 b))
)
; subtraction
(define-fun f16_sexp_sub ((a f16_sexp_t) (b f16_sexp_t)) f16_sexp_t
    (bvadd a (bvneg b))
)
; conversion
(define-fun f16_sexp_to_bv5 ((v f16_sexp_t)) bv5 ((_ extract 4 0) v))
(define-fun bv5_to_f16_sexp ((v bv5)) f16_sexp_t (concat #b000 v))
(define-fun f16_sexp_to_bv22 ((v f16_sexp_t)) bv22 (concat #b00000000000000 v))
(define-fun bv22_to_f16_sexp ((v bv22)) f16_sexp_t ((_ extract 7 0) v))
(define-fun bv11_to_bv22 ((v bv11)) bv22 (concat #b00000000000 v))
(define-fun bv22_to_bv11 ((v bv22)) bv11 ((_ extract 10 0) v))
(define-fun bv22_to_bv32 ((v bv22)) bv32 (concat #b0000000000 v))
(define-fun bv32_to_bv22 ((v bv32)) bv22 ((_ extract 21 0) v))
(define-fun bv16_to_bv32 ((v bv16)) bv32 (concat #x0000 v))
(define-fun bv32_to_bv16 ((v bv32)) bv16 ((_ extract 15 0) v))
(define-fun bv8_to_bv16 ((v bv8)) bv16 (concat #x00 v))
(define-fun bv16_to_bv8 ((v bv16)) bv8 ((_ extract 7 0) v))
(define-fun bv4_to_bv8 ((v bv4)) bv8 (concat #x0 v))
(define-fun bv8_to_bv4 ((v bv8)) bv4 ((_ extract 3 0) v))
(define-fun bv2_to_bv4 ((v bv2)) bv4 (concat #b00 v))
(define-fun bv4_to_bv2 ((v bv4)) bv2 ((_ extract 1 0) v))
(define-fun bv1_to_bv2 ((v bv1)) bv2 (concat #b0 v))
(define-fun bv2_to_bv1 ((v bv2)) bv1 ((_ extract 0 0) v))
; count-leading-zeros
(define-fun bv1_clz ((v bv1)) bv1
    (bvxor #b1 v)
)
(define-fun bv2_clz ((v bv2)) bv2
    (let
        ((shift (ite (bvult #b01 v) #b00 #b01)))
        (bvadd shift (bv1_to_bv2 (bv1_clz ((_ extract 1 1) (bvshl v shift)))))
    )
)
(define-fun bv4_clz ((v bv4)) bv4
    (let
        ((shift (ite (bvult #x3 v) #x0 #x2)))
        (bvadd shift (bv2_to_bv4 (bv2_clz ((_ extract 3 2) (bvshl v shift)))))
    )
)
(define-fun bv8_clz ((v bv8)) bv8
    (let
        ((shift (ite (bvult #x0F v) #x00 #x04)))
        (bvadd shift (bv4_to_bv8 (bv4_clz ((_ extract 7 4) (bvshl v shift)))))
    )
)
(define-fun bv16_clz ((v bv16)) bv16
    (let
        ((shift (ite (bvult #x00FF v) #x0000 #x0008)))
        (bvadd shift (bv8_to_bv16 (bv8_clz
                                   ((_ extract 15 8) (bvshl v shift)))))
    )
)
(define-fun bv32_clz ((v bv32)) bv32
    (let
        ((shift (ite (bvult #x0000FFFF v) #x00000000 #x00000010)))
        (bvadd shift (bv16_to_bv32 (bv16_clz
                                    ((_ extract 31 16) (bvshl v shift)))))
    )
)
(define-fun bv22_clz ((v bv22)) bv22
    (bv32_to_bv22 (bv32_clz (concat v #b0000000000)))
)
; shift right merging shifted out bits into the result's lsb
(define-fun bv22_lshr_merging ((v bv22) (shift bv22)) bv22
    ; did we shift out only zeros?
    (ite (= v (bvshl (bvlshr v shift) shift))
        ; yes. no adjustment needed
        (bvlshr v shift)
        ; no. set lsb
        (bvor (bvlshr v shift) #b0000000000000000000001)
    )
)

; field extraction functions
(define-fun f16_sign_field ((v bv16)) bv1 ((_ extract 15 15) v))
(define-fun f16_exponent_field ((v bv16)) bv5 ((_ extract 14 10) v))
(define-fun f16_mantissa_field ((v bv16)) bv10 ((_ extract 9 0) v))
(define-fun f16_mantissa_field_msb ((v bv16)) bv1 ((_ extract 9 9) v))
; construction from fields
(define-fun f16_from_fields ((sign_field bv1)
                            (exponent_field bv5)
                            (mantissa_field bv10)) bv16
    (concat sign_field exponent_field mantissa_field)
)
; handy constants
(define-fun f16_infinity ((sign_field bv1)) bv16
    (f16_from_fields sign_field #b11111 #b0000000000)
)
(define-fun f16_zero ((sign_field bv1)) bv16
    (f16_from_fields sign_field #b00000 #b0000000000)
)
; conversion to quiet NaN
(define-fun f16_into_qnan ((v bv16)) bv16
    (f16_from_fields
        (f16_sign_field v)
        #b11111
        (bvor #b1000000000 (f16_mantissa_field v))
    )
)
; conversion
(define-fun f16_to_fp ((v bv16)) Float16 ((_ to_fp 5 11) v))
; classification
(define-fun f16_is_nan ((v bv16)) Bool (fp.isNaN (f16_to_fp v)))
(define-fun f16_is_infinite ((v bv16)) Bool (fp.isInfinite (f16_to_fp v)))
(define-fun f16_is_normal ((v bv16)) Bool (fp.isNormal (f16_to_fp v)))
(define-fun f16_is_subnormal ((v bv16)) Bool (fp.isSubnormal (f16_to_fp v)))
(define-fun f16_is_zero ((v bv16)) Bool (fp.isZero (f16_to_fp v)))
(define-fun f16_is_qnan ((v bv16)) Bool
    (and (f16_is_nan v) (= (f16_mantissa_field_msb v) #b1))
)
; get mantissa value -- only correct for finite values
(define-fun f16_mantissa_value ((v bv16)) bv11
    (ite (f16_is_subnormal v)
        (concat #b0 (f16_mantissa_field v))
        (concat #b1 (f16_mantissa_field v))
    )
)
; f16 field values
(define-const f16_exponent_bias f16_sexp_t #x0F)
(define-const f16_max_exponent f16_sexp_t #x10)
(define-const f16_subnormal_exponent f16_sexp_t #xF2) ; -14
(define-fun f16_exponent_value ((v bv16)) f16_sexp_t
    (ite (= (f16_exponent_field v) #b00000)
        f16_subnormal_exponent
        (f16_sexp_sub
            (bv5_to_f16_sexp (f16_exponent_field v))
            f16_exponent_bias
        )
    )
)
; f16 mul
(define-fun f16_round_product_final_step_rne ((sign bv1)
                                             (product bv22)
                                             (exponent f16_sexp_t)
                                             (exponent_field bv5)) bv16
    ; if the exponent doesn't overflow
    (ite (f16_sexp_lt exponent f16_max_exponent)
        ; if we rounded a subnormal up to a normal
        (ite (and (= exponent_field #b00000) (not (bvult product #b1000000000000000000000)))
            (f16_from_fields
                sign
                #b00001
                ((_ extract 20 11) product)
            )
            (f16_from_fields
                sign
                exponent_field
                ((_ extract 20 11) product)
            )
        )
        (f16_infinity sign)
    )
)
(define-fun f16_round_product_rne ((sign bv1)
                                  (product bv22)
                                  (exponent f16_sexp_t)
                                  (exponent_field bv5)) bv16
    (let
        (
            (half_way (= (bv22_to_bv11 product) #b10000000000))
            (is_even (= ((_ extract 11 11) product) #b0))
            (rounded_up (bvadd product (bv11_to_bv22 #b10000000000)))
        )
        (let
            (
                (round_up_overflows (bvult rounded_up product))
                (do_round_up
                    (ite half_way
                        (not is_even)
                        (bvult #b10000000000 (bv22_to_bv11 product))
                    )
                )
            )
            (ite do_round_up
                (ite round_up_overflows
                    (f16_round_product_final_step_rne
                        sign
                        (bvor
                            (bvlshr rounded_up #b0000000000000000000001)
                            #b1000000000000000000000
                        )
                        (bvadd exponent #x01)
                        (bvadd exponent_field #b00001)
                    )
                    (f16_round_product_final_step_rne
                        sign rounded_up exponent exponent_field)
                )
                (f16_round_product_final_step_rne
                    sign product exponent exponent_field)
            )
        )
    )
)
(define-fun f16_mul_nonzero_finite_rne ((a bv16) (b bv16)) bv16
    (let
        (
            (product (bvmul (bv11_to_bv22 (f16_mantissa_value a))
                            (bv11_to_bv22 (f16_mantissa_value b))))
            (sign (bvxor (f16_sign_field a) (f16_sign_field b)))
            (exponent (bvadd (f16_exponent_value a) (f16_exponent_value b)))
        )
        ; normalize product
        (let
            (
                (norm_product (bvshl product (bv22_clz product)))
                (norm_exponent
                    (bvadd
                        exponent

                        ; compensation for product changing from having two
                        ; integer-part bits to one by normalization
                        #x01

                        (bvneg (bv22_to_f16_sexp (bv22_clz product)))
                    )
                )
            )
            (let
                (
                    ; amount to shift norm_product right to de-normalize again
                    ; for subnormals
                    (subnormal_shift
                        (f16_sexp_sub f16_subnormal_exponent norm_exponent)
                    )
                )
                ; if subnormal_shift would not cause the mantissa to overflow
                (ite (f16_sexp_lt #x00 subnormal_shift)
                    ; subnormals:
                    (f16_round_product_rne
                        sign
                        (bv22_lshr_merging
                            norm_product
                            (f16_sexp_to_bv22 subnormal_shift)
                        )
                        f16_subnormal_exponent
                        #b00000
                    )
                    ; normals:
                    (f16_round_product_rne
                        sign
                        norm_product
                        norm_exponent
                        (f16_sexp_to_bv5 (bvadd norm_exponent
                                          f16_exponent_bias))
                    )
                )
            )
        )
    )
)

(define-fun f16_mul_rne ((a bv16) (b bv16)) bv16
    (ite (f16_is_nan a)
        (f16_into_qnan a)
        (ite (f16_is_nan b)
            (f16_into_qnan b)
            (ite
                (or
                    (and (f16_is_zero a) (f16_is_infinite b))
                    (and (f16_is_infinite a) (f16_is_zero b))
                )
                #x7E00
                (ite (or (f16_is_infinite a) (f16_is_infinite b))
                    (f16_infinity (bvxor (f16_sign_field a) (f16_sign_field b)))
                    (ite (or (f16_is_zero a) (f16_is_zero b))
                        (f16_zero (bvxor (f16_sign_field a) (f16_sign_field b)))
                        (f16_mul_nonzero_finite_rne a b)
                    )
                )
            )
        )
    )
)

; input values in ieee754 f16 format as bit-vectors
(declare-const a bv16)
(declare-const b bv16)
; product for debugging
(declare-const p bv16)
(assert (= (f16_to_fp p) (fp.mul RNE (f16_to_fp a) (f16_to_fp b))))
; intermediate values from f16_mul_nonzero_finite_rne for debugging
(define-const product bv22 (bvmul (bv11_to_bv22 (f16_mantissa_value a))
                (bv11_to_bv22 (f16_mantissa_value b))))
(define-const sign bv1 (bvxor (f16_sign_field a) (f16_sign_field b)))
(define-const exponent f16_sexp_t (bvadd (f16_exponent_value a) (f16_exponent_value b)))
(define-const norm_product bv22 (bvshl product (bv22_clz product)))
(define-const norm_exponent f16_sexp_t
    (bvadd
        exponent

        ; compensation for product changing from having two
        ; integer-part bits to one by normalization
        #x01

        (bvneg (bv22_to_f16_sexp (bv22_clz product)))
    )
)
(define-const subnormal_shift f16_sexp_t
    (f16_sexp_sub f16_subnormal_exponent norm_exponent)
)
; intermediate values from f16_round_product_rne when the result is subnormal:
(define-const product_subnormal bv22
    (bv22_lshr_merging
        norm_product
        (f16_sexp_to_bv22 subnormal_shift)
    )
)
(define-const half_way_subnormal Bool
    (= (bv22_to_bv11 product_subnormal) #b10000000000))
(define-const is_even_subnormal Bool
    (= ((_ extract 11 11) product_subnormal) #b0))
(define-const rounded_up_subnormal bv22
    (bvadd product_subnormal (bv11_to_bv22 #b10000000000)))
(define-const round_up_overflows_subnormal Bool
    (bvult rounded_up_subnormal product_subnormal))
(define-const do_round_up_subnormal Bool
    (ite half_way_subnormal
        (not is_even_subnormal)
        (bvult #b10000000000 (bv22_to_bv11 product_subnormal))
    )
)
; intermediate values from f16_round_product_rne when the result is normal:
(define-const exponent_field_normal bv5
    (f16_sexp_to_bv5 (bvadd norm_exponent f16_exponent_bias))
)
(define-const half_way_normal Bool (= (bv22_to_bv11 norm_product) #b10000000000))
(define-const is_even_normal Bool (= ((_ extract 11 11) norm_product) #b0))
(define-const rounded_up_normal bv22
    (bvadd norm_product (bv11_to_bv22 #b10000000000))
)
(define-const round_up_overflows_normal Bool (bvult rounded_up_normal norm_product))
(define-const do_round_up_normal Bool
    (ite half_way_normal
        (not is_even_normal)
        (bvult #b10000000000 (bv22_to_bv11 norm_product))
    )
)



; now look for a case where f16_mul_rne is broke:
(assert (not (=
    (f16_to_fp (f16_mul_rne a b))
    (fp.mul RNE (f16_to_fp a) (f16_to_fp b))
)))
; should return unsat, meaning there aren't any broken cases
(echo "should return unsat:")
(check-sat)
(echo "dumping values in case it returned sat:")
(get-value (
    a
    b
    p
    (f16_to_fp a)
    (f16_to_fp b)
    (fp.mul RNE (f16_to_fp a) (f16_to_fp b))
    (f16_to_fp (f16_mul_rne a b))
    (f16_mul_nonzero_finite_rne a b)
    (f16_mantissa_field a)
    (f16_mantissa_value a)
    (f16_mantissa_field b)
    (f16_mantissa_value b)
    product
    sign
    exponent
    (bv22_clz product)
    norm_product
    norm_exponent
    subnormal_shift
    product_subnormal
    half_way_subnormal
    is_even_subnormal
    rounded_up_subnormal
    round_up_overflows_subnormal
    do_round_up_subnormal
    exponent_field_normal
    half_way_normal
    is_even_normal
    rounded_up_normal
    round_up_overflows_normal
    do_round_up_normal
))