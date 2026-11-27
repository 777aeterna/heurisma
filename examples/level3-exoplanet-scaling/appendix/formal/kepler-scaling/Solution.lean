import Challenge

-- Machine-checked proof (`0` `sorry`, standard axioms only; verified for type equality against Challenge)
namespace Solution

theorem kepler_two_body_scaling
    (P1 P2 a1 a2 GM1 GM2 k s m : Int)
    (hk : k ≠ 0) (hGM : GM2 ≠ 0) (ha : a2 ≠ 0)
    (hs : GM1 = s * GM2) (hm : a1 = m * a2)
    (h1 : P1 * P1 * GM1 = k * (a1 * a1 * a1))
    (h2 : P2 * P2 * GM2 = k * (a2 * a2 * a2)) :
    P1 * P1 * s = P2 * P2 * (m * m * m) := by
  have ha3 : a2 * a2 * a2 ≠ 0 := Int.mul_ne_zero (Int.mul_ne_zero ha ha) ha
  have hka3 : k * (a2 * a2 * a2) ≠ 0 := Int.mul_ne_zero hk ha3
  have h_scaled :
      (P1 * P1 * s) * (k * (a2 * a2 * a2)) =
      (P2 * P2 * (m * m * m)) * (k * (a2 * a2 * a2)) := by
    calc
      (P1 * P1 * s) * (k * (a2 * a2 * a2))
          = (P1 * P1 * s) * (P2 * P2 * GM2) := by rw [← h2]
      _   = (P1 * P1 * (s * GM2)) * (P2 * P2) := by
              rw [Int.mul_assoc (P1 * P1) s (P2 * P2 * GM2)]
              rw [Int.mul_comm (P2 * P2) GM2]
              rw [← Int.mul_assoc s GM2 (P2 * P2)]
              rw [← Int.mul_assoc (P1 * P1) (s * GM2) (P2 * P2)]
      _   = (P1 * P1 * GM1) * (P2 * P2) := by rw [← hs]
      _   = (k * (a1 * a1 * a1)) * (P2 * P2) := by rw [h1]
      _   = (k * ((m * a2) * (m * a2) * (m * a2))) * (P2 * P2) := by rw [hm]
      _   = (k * ((m * m * m) * (a2 * a2 * a2))) * (P2 * P2) := by
              have hcube : (m * a2) * (m * a2) * (m * a2) = (m * m * m) * (a2 * a2 * a2) := by
                simp only [Int.mul_assoc, Int.mul_left_comm, Int.mul_comm]
              rw [hcube]
      _   = (P2 * P2 * (m * m * m)) * (k * (a2 * a2 * a2)) := by
              simp only [Int.mul_assoc, Int.mul_left_comm, Int.mul_comm]
  have h_pos_gm : GM2 = GM2 := rfl
  exact Int.eq_of_mul_eq_mul_right hka3 h_scaled

end Solution
