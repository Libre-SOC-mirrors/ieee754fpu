; SPDX-License-Identifier: LGPL-2.1-or-later

; Test to see if using smt-lib2's floating-point support for checking fpu hw
; is feasible by implementing fp multiplication with bit-vectors and seeing if
; the smt checkers work. The idea is we can run this test before putting in
; all the effort to add support in yosys and nmigen for smtlib2 reals and
; floating-point numbers.

; run with: z3 -smt2 fpmul_test.smt2

; create some handy type aliases
(define-sort bv1 () (_ BitVec 1))
(define-sort bv2 () (_ BitVec 2))
(define-sort bv4 () (_ BitVec 4))
(define-sort bv8 () (_ BitVec 8))
(define-sort bv16 () (_ BitVec 16))
(define-sort bv23 () (_ BitVec 23))
(define-sort bv24 () (_ BitVec 24))
(define-sort bv32 () (_ BitVec 32))
(define-sort bv48 () (_ BitVec 48))

; type for signed f32 exponents
(define-sort f32_sexp_t () (_ BitVec 12))
; signed less-than comparison
(define-fun f32_sexp_lt ((a f32_sexp_t) (b f32_sexp_t)) Bool
    (bvult (bvxor #x800 a) (bvxor #x800 b))
)
; subtraction
(define-fun f32_sexp_sub ((a f32_sexp_t) (b f32_sexp_t)) f32_sexp_t
    (bvadd a (bvneg b))
)
; conversion
(define-fun f32_sexp_to_bv8 ((v f32_sexp_t)) bv8 ((_ extract 7 0) v))
(define-fun bv8_to_f32_sexp ((v bv8)) f32_sexp_t (concat #x0 v))
(define-fun f32_sexp_to_bv48 ((v f32_sexp_t)) bv48 (concat #x000000000 v))
(define-fun bv48_to_f32_sexp ((v bv48)) f32_sexp_t ((_ extract 11 0) v))
(define-fun bv24_to_bv48 ((v bv24)) bv48 (concat #x000000 v))
(define-fun bv48_to_bv24 ((v bv48)) bv24 ((_ extract 23 0) v))
(define-fun bv32_to_bv48 ((v bv32)) bv48 (concat #x0000 v))
(define-fun bv48_to_bv32 ((v bv48)) bv32 ((_ extract 31 0) v))
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
(define-fun bv48_clz ((v bv48)) bv48
    (let
        ((shift (ite (bvult #x00000000FFFF v) #x000000000000 #x000000000010)))
        (bvadd shift (bv32_to_bv48 (bv32_clz
                                    ((_ extract 47 16) (bvshl v shift)))))
    )
)
; shift right merging shifted out bits into the result's lsb
(define-fun bv48_lshr_merging ((v bv48) (shift bv48)) bv48
    ; did we shift out only zeros?
    (ite (= v (bvshl (bvlshr v shift) shift))
        ; yes. no adjustment needed
        (bvlshr v shift)
        ; no. set lsb
        (bvor (bvlshr v shift) #x000000000001)
    )
)

; field extraction functions
(define-fun f32_sign_field ((v bv32)) bv1 ((_ extract 31 31) v))
(define-fun f32_exponent_field ((v bv32)) bv8 ((_ extract 30 23) v))
(define-fun f32_mantissa_field ((v bv32)) bv23 ((_ extract 22 0) v))
(define-fun f32_mantissa_field_msb ((v bv32)) bv1 ((_ extract 22 22) v))
; construction from fields
(define-fun f32_from_fields ((sign_field bv1)
                            (exponent_field bv8)
                            (mantissa_field bv23)) bv32
    (concat sign_field exponent_field mantissa_field)
)
; handy constants
(define-fun f32_infinity ((sign_field bv1)) bv32
    (f32_from_fields sign_field #xFF #b00000000000000000000000)
)
(define-fun f32_zero ((sign_field bv1)) bv32
    (f32_from_fields sign_field #x00 #b00000000000000000000000)
)
; conversion to quiet NaN
(define-fun f32_into_qnan ((v bv32)) bv32
    (f32_from_fields
        (f32_sign_field v)
        #xFF
        (bvor #b10000000000000000000000 (f32_mantissa_field v))
    )
)
; conversion
(define-fun f32_to_fp ((v bv32)) Float32 ((_ to_fp 8 24) v))
; classification
(define-fun f32_is_nan ((v bv32)) Bool (fp.isNaN (f32_to_fp v)))
(define-fun f32_is_infinite ((v bv32)) Bool (fp.isInfinite (f32_to_fp v)))
(define-fun f32_is_normal ((v bv32)) Bool (fp.isNormal (f32_to_fp v)))
(define-fun f32_is_subnormal ((v bv32)) Bool (fp.isSubnormal (f32_to_fp v)))
(define-fun f32_is_zero ((v bv32)) Bool (fp.isZero (f32_to_fp v)))
(define-fun f32_is_qnan ((v bv32)) Bool
    (and (f32_is_nan v) (= (f32_mantissa_field_msb v) #b1))
)
; get mantissa value -- only correct for finite values
(define-fun f32_mantissa_value ((v bv32)) bv24
    (ite (f32_is_subnormal v)
        (concat #b0 (f32_mantissa_field v))
        (concat #b1 (f32_mantissa_field v))
    )
)
; f32 field values
(define-const f32_exponent_bias f32_sexp_t #x07F)
(define-const f32_max_exponent f32_sexp_t #x080)
(define-const f32_subnormal_exponent f32_sexp_t #xF82) ; -126
(define-fun f32_exponent_value ((v bv32)) f32_sexp_t
    (ite (= (f32_exponent_field v) #x00)
        f32_subnormal_exponent
        (f32_sexp_sub
            (bv8_to_f32_sexp (f32_exponent_field v))
            f32_exponent_bias
        )
    )
)
; f32 mul
(define-fun f32_round_product_final_step_rne ((sign bv1)
                                             (product bv48)
                                             (exponent f32_sexp_t)
                                             (exponent_field bv8)) bv32
    ; if the exponent doesn't overflow
    (ite (f32_sexp_lt exponent f32_max_exponent)
        ; if we rounded a subnormal up to a normal
        (ite (and (= exponent_field #x00) (not (bvult product #x800000000000)))
            (f32_from_fields
                sign
                #x01
                ((_ extract 46 24) product)
            )
            (f32_from_fields
                sign
                exponent_field
                ((_ extract 46 24) product)
            )
        )
        (f32_infinity sign)
    )
)
(define-fun f32_round_product_rne ((sign bv1)
                                  (product bv48)
                                  (exponent f32_sexp_t)
                                  (exponent_field bv8)) bv32
    (let
        (
            (half_way (= (bv48_to_bv24 product) #x800000))
            (is_even (= ((_ extract 24 24) product) #b0))
            (rounded_up (bvadd product (bv24_to_bv48 #x800000)))
        )
        (let
            (
                (round_up_overflows (bvult rounded_up product))
                (do_round_up
                    (ite half_way
                        (not is_even)
                        (bvult #x800000 (bv48_to_bv24 product))
                    )
                )
            )
            (ite do_round_up
                (ite round_up_overflows
                    (f32_round_product_final_step_rne
                        sign
                        (bvor
                            (bvlshr rounded_up #x000000000001)
                            #x800000000000
                        )
                        (bvadd exponent #x001)
                        (bvadd exponent_field #x01)
                    )
                    (f32_round_product_final_step_rne
                        sign rounded_up exponent exponent_field)
                )
                (f32_round_product_final_step_rne
                    sign product exponent exponent_field)
            )
        )
    )
)
(define-fun f32_mul_nonzero_finite_rne ((a bv32) (b bv32)) bv32
    (let
        (
            (product (bvmul (bv24_to_bv48 (f32_mantissa_value a))
                            (bv24_to_bv48 (f32_mantissa_value b))))
            (sign (bvxor (f32_sign_field a) (f32_sign_field b)))
            (exponent (bvadd (f32_exponent_value a) (f32_exponent_value b)))
        )
        ; normalize product
        (let
            (
                (norm_product (bvshl product (bv48_clz product)))
                (norm_exponent
                    (bvadd
                        exponent

                        ; compensation for product changing from having two
                        ; integer-part bits to one by normalization
                        #x001

                        (bvneg (bv48_to_f32_sexp (bv48_clz product)))
                    )
                )
            )
            (let
                (
                    ; amount to shift norm_product right to de-normalize again
                    ; for subnormals
                    (subnormal_shift
                        (f32_sexp_sub f32_subnormal_exponent norm_exponent)
                    )
                )
                ; if subnormal_shift would not cause the mantissa to overflow
                (ite (f32_sexp_lt #x000 subnormal_shift)
                    ; subnormals:
                    (f32_round_product_rne
                        sign
                        (bvadd
                            (bv48_lshr_merging
                                norm_product
                                (f32_sexp_to_bv48 subnormal_shift)
                            )
                        )
                        f32_subnormal_exponent
                        #x00
                    )
                    ; normals:
                    (f32_round_product_rne
                        sign
                        norm_product
                        norm_exponent
                        (f32_sexp_to_bv8 (bvadd norm_exponent
                                          f32_exponent_bias))
                    )
                )
            )
        )
    )
)

(define-fun f32_mul_rne ((a bv32) (b bv32)) bv32
    (ite (f32_is_nan a)
        (f32_into_qnan a)
        (ite (f32_is_nan b)
            (f32_into_qnan b)
            (ite
                (or
                    (and (f32_is_zero a) (f32_is_infinite b))
                    (and (f32_is_infinite a) (f32_is_zero b))
                )
                #x7FC00000
                (ite (or (f32_is_infinite a) (f32_is_infinite b))
                    (f32_infinity (bvxor (f32_sign_field a) (f32_sign_field b)))
                    (ite (or (f32_is_zero a) (f32_is_zero b))
                        (f32_zero (bvxor (f32_sign_field a) (f32_sign_field b)))
                        (f32_mul_nonzero_finite_rne a b)
                    )
                )
            )
        )
    )
)

; input values in ieee754 f32 format as bit-vectors
(declare-const a bv32)
(declare-const b bv32)
; product for debugging
(declare-const p bv32)
(assert (= (f32_to_fp p) (fp.mul RNE (f32_to_fp a) (f32_to_fp b))))
; intermediate values from f32_mul_nonzero_finite_rne for debugging
(define-const product bv48 (bvmul (bv24_to_bv48 (f32_mantissa_value a))
                (bv24_to_bv48 (f32_mantissa_value b))))
(define-const sign bv1 (bvxor (f32_sign_field a) (f32_sign_field b)))
(define-const exponent f32_sexp_t (bvadd (f32_exponent_value a) (f32_exponent_value b)))
(define-const norm_product bv48 (bvshl product (bv48_clz product)))
(define-const norm_exponent f32_sexp_t
    (bvadd
        exponent

        ; compensation for product changing from having two
        ; integer-part bits to one by normalization
        #x001

        (bvneg (bv48_to_f32_sexp (bv48_clz product)))
    )
)
(define-const subnormal_shift f32_sexp_t
    (f32_sexp_sub f32_subnormal_exponent norm_exponent)
)
; intermediate values from f32_round_product_rne when the result is subnormal:
(define-const product_subnormal bv48
    (bv48_lshr_merging
        norm_product
        (f32_sexp_to_bv48 subnormal_shift)
    )
)
(define-const half_way_subnormal Bool
    (= (bv48_to_bv24 product_subnormal) #x800000))
(define-const is_even_subnormal Bool
    (= ((_ extract 24 24) product_subnormal) #b0))
(define-const rounded_up_subnormal bv48
    (bvadd product_subnormal (bv24_to_bv48 #x800000)))
(define-const round_up_overflows_subnormal Bool
    (bvult rounded_up_subnormal product_subnormal))
(define-const do_round_up_subnormal Bool
    (ite half_way_subnormal
        (not is_even_subnormal)
        (bvult #x800000 (bv48_to_bv24 product_subnormal))
    )
)
; intermediate values from f32_round_product_rne when the result is normal:
(define-const exponent_field_normal bv8
    (f32_sexp_to_bv8 (bvadd norm_exponent f32_exponent_bias))
)
(define-const half_way_normal Bool (= (bv48_to_bv24 norm_product) #x800000))
(define-const is_even_normal Bool (= ((_ extract 24 24) norm_product) #b0))
(define-const rounded_up_normal bv48
    (bvadd norm_product (bv24_to_bv48 #x800000))
)
(define-const round_up_overflows_normal Bool (bvult rounded_up_normal norm_product))
(define-const do_round_up_normal Bool
    (ite half_way_normal
        (not is_even_normal)
        (bvult #x800000 (bv48_to_bv24 norm_product))
    )
)



; now look for a case where f32_mul_rne is broke:
(assert (not (=
    (f32_to_fp (f32_mul_rne a b))
    (fp.mul RNE (f32_to_fp a) (f32_to_fp b))
)))
; should return unsat, meaning there aren't any broken cases
(echo "should return unsat:")
(check-sat)
(echo "dumping values in case it returned sat:")
(get-value (
    a
    b
    p
    (f32_to_fp a)
    (f32_to_fp b)
    (fp.mul RNE (f32_to_fp a) (f32_to_fp b))
    (f32_to_fp (f32_mul_rne a b))
    (f32_mul_nonzero_finite_rne a b)
    (f32_mantissa_field a)
    (f32_mantissa_value a)
    (f32_mantissa_field b)
    (f32_mantissa_value b)
    product
    sign
    exponent
    (bv48_clz product)
    (ite (bvult #x00000000FFFF product) #x000000000000 #x000000000010)
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