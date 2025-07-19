# CNC Tool Measurer Pro 🛠️📏

**CNC Tool Measurer Pro** is a Python-based desktop application designed to accurately measure CNC tool components using image analysis. The system uses OpenCV for image processing and Tkinter for a user-friendly interface.

---

## 🎥 Demo

Here’s a quick preview of how the CNC Tool Measurer works:

![CNC Tool Measurer Demo](Demo.gif)

## 🔍 Features

- 📸 **Camera & Upload Modes** – Capture or load top/side views of tools
- 🔄 **Reference Scaling** – Uses ₹10 coin or other object for real-world scaling
- 📏 **Measure Dimensions** – Inner diameter, outer diameter, height
- 🧠 **Smart Detection** – Automatic contour and shape recognition
- 🧪 **Sharpness Check** – Ensures input image is of usable quality
- 💾 **Export Results** – Save measurements to Excel/CSV
- 🧰 **Serial Port Ready** – Can be expanded to work with Arduino/CMMs

---

## 🖥️ GUI Preview

> The GUI features a multi-tab interface, with options for:
- Image selection/capture
- Manual & auto detection
- Measurement display
- Export & Reset

---

## 🧠 Technologies Used

- **Python 3.x**
- **OpenCV**
- **Tkinter**
- **PIL (Pillow)**
- **NumPy**
- **Serial (pyserial)**
- **CSV & Excel Export**

---

## 🛠️ How to Run

1. Clone this repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd YOUR_REPO_NAME
````

2. Install dependencies:

   ```bash
   pip install opencv-python numpy pillow pyserial
   ```

3. Run the notebook:

   ```bash
   jupyter notebook toolFMM.ipynb
   ```

   Or convert the notebook to `.py` using:

   ```bash
   jupyter nbconvert --to script toolFMM.ipynb
   python toolFMM.py
   ```

---

## 📂 Folder Structure (recommended)

```
CNC-Tool-Measurer/
│
├── toolFMM.ipynb       # Notebook with visual explanation
├── toolFMM.py          # Python script for direct execution
├── demo.gif            # GIF demo of the tool in action
├── README.md           # Project documentation
├── requirements.txt    # (Optional) Dependencies list
├── LICENSE             # (Optional) License file
```

---

## 📈 Future Improvements

* Auto-calibration using multiple reference coins
* Integration with CMM machines
* AI-based shape classification
* Multi-angle stitching

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## ✍️ Author

**Rakshit Ojhaa**
*Developer, Lifter, Builder*
