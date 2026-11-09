"""
Sample handwritten-form reader (FAKE data only).

Safety rule: if the result is unclear (no box ticked, two boxes ticked, or the
circle is too close to call) the script says NEEDS HUMAN REVIEW instead of
guessing. A person must always confirm the result before it is used.
"""
import os
import cv2
import numpy as np

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(OUT_DIR, "sample_handwritten_form.png")

INK_THRESHOLD = 180      # pixel darker than this counts as ink
CHECK_MIN_INK = 20       # min ink pixels inside a box to count as ticked
CIRCLE_MIN_RATIO = 1.25  # winning side must have 25% more ink than the other

OPTIONS = [
    {"name": "Semaglutide 1.0 mg", "box": (40, 110, 60, 130)},
    {"name": "Tirzepatide 15 mg",  "box": (40, 150, 60, 170)},
    {"name": "Liraglutide 3.0 mg", "box": (40, 190, 60, 210)},
]
CLINIC_REGION = (160, 230)    # x range
PATIENT_REGION = (250, 335)   # x range
DEST_Y = (240, 270)


def make_sample_image():
    img = np.ones((450, 480, 3), dtype=np.uint8) * 255
    cv2.putText(img, "Weight Loss Prescription Slip", (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "Patient: Sample Patient", (40, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    for opt in OPTIONS:
        x1, y1, x2, y2 = opt["box"]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), 2)
        cv2.putText(img, opt["name"], (x2 + 15, y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    # handwritten cross in the Tirzepatide box
    cv2.line(img, (42, 152), (58, 168), (15, 15, 15), 2)
    cv2.line(img, (42, 168), (58, 152), (15, 15, 15), 2)
    cv2.putText(img, "DELIVER TO:   CLINIC     PATIENT", (40, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.ellipse(img, (290, 255), (42, 16), 0, 0, 360, (20, 20, 20), 2)
    return img


def ink_count(gray, y1, y2, x1, x2):
    region = gray[y1:y2, x1:x2]
    _, thresh = cv2.threshold(region, INK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    return int(cv2.countNonZero(thresh))


def read_checkboxes(gray):
    """Returns (selected_name or None, list of (name, ink), needs_review)."""
    results, ticked = [], []
    for opt in OPTIONS:
        x1, y1, x2, y2 = opt["box"]
        ink = ink_count(gray, y1 + 3, y2 - 3, x1 + 3, x2 - 3)  # ignore outer border
        results.append((opt["name"], ink))
        if ink > CHECK_MIN_INK:
            ticked.append(opt["name"])
    if len(ticked) == 1:
        return ticked[0], results, False
    return None, results, True   # none or several ticked -> human must decide


def read_destination(gray):
    clinic = ink_count(gray, DEST_Y[0], DEST_Y[1], *CLINIC_REGION)
    patient = ink_count(gray, DEST_Y[0], DEST_Y[1], *PATIENT_REGION)
    hi, lo = max(clinic, patient), max(min(clinic, patient), 1)
    if hi / lo < CIRCLE_MIN_RATIO:
        return None, clinic, patient, True
    return ("PATIENT" if patient > clinic else "CLINIC"), clinic, patient, False


def main():
    img = make_sample_image()
    cv2.imwrite(OUT_PNG, img)
    print(f"--> Sample form saved as '{OUT_PNG}'")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    print("\n--- Scanning Checkboxes ---")
    medicine, rows, review_med = read_checkboxes(gray)
    for name, ink in rows:
        print(f"{'[CHECKED]' if ink > CHECK_MIN_INK else '[ ]':9} {name} (ink pixels: {ink})")

    print("\n--- Scanning Circled Text ---")
    dest, clinic, patient, review_dest = read_destination(gray)
    print(f"Ink  clinic={clinic}  patient={patient}")

    print("\n" + "=" * 45)
    print("EXTRACTED DATA (a person must confirm before use):")
    print(f"Selected Medicine : {medicine or 'NEEDS HUMAN REVIEW'}")
    print(f"Delivery Target   : {dest or 'NEEDS HUMAN REVIEW'}")
    print("=" * 45)


if __name__ == "__main__":
    main()
