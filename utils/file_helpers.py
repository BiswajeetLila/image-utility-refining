from tkinter import filedialog

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tga", ".tiff"}

IMAGE_FILETYPES = [
    ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp *.tga *.tiff"),
    ("All files", "*.*"),
]


def ask_open_image():
    return filedialog.askopenfilename(filetypes=IMAGE_FILETYPES)


def ask_open_folder():
    return filedialog.askdirectory()


def ask_save_image():
    return filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG", "*.png"), ("All files", "*.*")],
    )
