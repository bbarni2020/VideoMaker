import os
import glob
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from moviepy import ImageSequenceClip, ImageClip, concatenate_videoclips
from PIL import Image
import argparse
import threading
import time
from pillow_heif import register_heif_opener

register_heif_opener()

def get_image_files(folder_path):
    image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif', '*.tiff', '*.heic', '*.webp']
    image_files = []
    for extension in image_extensions:
        pattern = os.path.join(folder_path, '**', extension)
        image_files.extend(glob.glob(pattern, recursive=True))
        pattern = os.path.join(folder_path, '**', extension.upper())
        image_files.extend(glob.glob(pattern, recursive=True))
    image_files = sorted(list(set(image_files)))
    return image_files

def resize_and_pad_image(image_path, target_width=1920, target_height=1080):
    try:
        with Image.open(image_path) as img:

            img.load()

            if img.mode in ('RGBA', 'LA'):

                background = Image.new('RGB', img.size, (0, 0, 0))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            

            clean_img = Image.new('RGB', img.size)
            clean_img.putdata(list(img.getdata()))
            img = clean_img
            

            if img.height > img.width:

                canvas_size = img.height
                square_img = Image.new('RGB', (canvas_size, canvas_size), (0, 0, 0))

                paste_x = (canvas_size - img.width) // 2
                paste_y = 0
                square_img.paste(img, (paste_x, paste_y))
                img = square_img
            
            img_ratio = img.width / img.height
            target_ratio = target_width / target_height
            
            if abs(img_ratio - target_ratio) < 0.01:
                resized_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                temp_path = image_path.replace(os.path.splitext(image_path)[1], '_temp.jpg')

                resized_img.save(temp_path, 'JPEG', quality=95, exif=b'', optimize=True)
                return temp_path
            else:
                ratio = min(target_width / img.width, target_height / img.height)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                final_img = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                paste_x = (target_width - new_width) // 2
                paste_y = (target_height - new_height) // 2
                final_img.paste(resized_img, (paste_x, paste_y))
                
                temp_path = image_path.replace(os.path.splitext(image_path)[1], '_temp.jpg')

                final_img.save(temp_path, 'JPEG', quality=95, exif=b'', optimize=True)
                return temp_path
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return image_path

def create_video_from_images(image_folder, output_path, duration_per_image, fps=24, progress_callback=None):
    if progress_callback:
        progress_callback("Searching for images...", 0)
    
    image_files = get_image_files(image_folder)
    if not image_files:
        raise ValueError("No image files found in the specified folder!")
    
    if progress_callback:
        progress_callback(f"Found {len(image_files)} image files", 5)
    
    clips = []
    temp_files = []
    total_images = len(image_files)
    
    try:
        for i, image_path in enumerate(image_files):
            if progress_callback:
                progress = 5 + (i / total_images) * 60
                progress_callback(f"Processing image {i+1}/{total_images}: {os.path.basename(image_path)}", progress)
            
            processed_image = resize_and_pad_image(image_path)
            if processed_image != image_path:
                temp_files.append(processed_image)
            clip = ImageClip(processed_image, duration=duration_per_image)
            clips.append(clip)
        
        if progress_callback:
            progress_callback("Creating video...", 70)
        
        final_video = concatenate_videoclips(clips, method="compose")
        
        if progress_callback:
            progress_callback("Encoding video file...", 80)
        
        final_video.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio=False
        )
        
        if progress_callback:
            progress_callback(f"Video created successfully! Duration: {len(clips) * duration_per_image:.2f} seconds", 100)
        
    finally:
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"Warning: Could not remove temporary file {temp_file}: {e}")

class VideoMakerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VideoMaker - Image to Video Converter")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        self.image_folder = tk.StringVar()
        self.output_path = tk.StringVar()
        self.duration_var = tk.DoubleVar(value=2.0)
        self.fps_var = tk.IntVar(value=24)
        self.is_processing = False
        
        self.create_widgets()
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        title_label = ttk.Label(main_frame, text="VideoMaker", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        ttk.Label(main_frame, text="Input Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.image_folder, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 5), pady=5)
        ttk.Button(main_frame, text="Browse", command=self.select_input_folder).grid(row=1, column=2, pady=5)
        
        ttk.Label(main_frame, text="Output Video:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_path, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 5), pady=5)
        ttk.Button(main_frame, text="Browse", command=self.select_output_path).grid(row=2, column=2, pady=5)
        
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20)
        settings_frame.columnconfigure(1, weight=1)
        
        ttk.Label(settings_frame, text="Duration per Image (seconds):").grid(row=0, column=0, sticky=tk.W, pady=5)
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        ttk.Scale(duration_frame, from_=0.1, to=10.0, variable=self.duration_var, orient=tk.HORIZONTAL, length=200).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Entry(duration_frame, textvariable=self.duration_var, width=5).grid(row=0, column=1, padx=(10, 5))
        ttk.Label(duration_frame, textvariable=self.duration_var).grid(row=0, column=2, padx=(5, 0))
        duration_frame.columnconfigure(0, weight=1)
        
        ttk.Label(settings_frame, text="Frames per Second:").grid(row=1, column=0, sticky=tk.W, pady=5)
        fps_frame = ttk.Frame(settings_frame)
        fps_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        ttk.Scale(fps_frame, from_=15, to=60, variable=self.fps_var, orient=tk.HORIZONTAL, length=200).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Entry(fps_frame, textvariable=self.fps_var, width=5).grid(row=0, column=1, padx=(10, 5))
        ttk.Label(fps_frame, textvariable=self.fps_var).grid(row=0, column=2, padx=(5, 0))
        fps_frame.columnconfigure(0, weight=1)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=20)
        
        self.start_button = ttk.Button(button_frame, text="Start Video Creation", command=self.start_video_creation, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_operation, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        self.cleanup_button = ttk.Button(button_frame, text="Delete Temp Files", command=self.delete_temp_files)
        self.cleanup_button.pack(side=tk.LEFT, padx=5)
        
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.StringVar(value="Ready to start...")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding="10")
        info_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        
        self.info_text = tk.Text(info_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=scrollbar.set)
        
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        main_frame.rowconfigure(6, weight=1)
        
        self.update_duration_display()
        self.update_fps_display()
        
    def update_duration_display(self):
        self.duration_var.set(round(self.duration_var.get(), 1))
        self.root.after(100, self.update_duration_display)
        
    def update_fps_display(self):
        self.fps_var.set(int(self.fps_var.get()))
        self.root.after(100, self.update_fps_display)
        
    def log_info(self, message):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.info_text.see(tk.END)
        self.info_text.config(state=tk.DISABLED)
        
    def select_input_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing images")
        if folder:
            self.image_folder.set(folder)
            self.log_info(f"Selected input folder: {folder}")
            
            if not self.output_path.get():
                default_output = os.path.join(folder, "output_video.mp4")
                self.output_path.set(default_output)
                
    def select_output_path(self):
        file_path = filedialog.asksaveasfilename(
            title="Save video as...",
            defaultextension=".mp4",
            filetypes=[
                ("MP4 files", "*.mp4"),
                ("AVI files", "*.avi"),
                ("MOV files", "*.mov"),
                ("All files", "*.*")
            ],
            initialdir=self.image_folder.get() if self.image_folder.get() else os.getcwd()
        )
        if file_path:
            self.output_path.set(file_path)
            self.log_info(f"Selected output path: {file_path}")
            
    def update_progress(self, message, progress):
        self.progress_var.set(message)
        self.progress_bar['value'] = progress
        self.log_info(message)
        self.root.update_idletasks()
        
    def start_video_creation(self):
        if not self.image_folder.get():
            messagebox.showerror("Error", "Please select an input folder!")
            return
            
        if not self.output_path.get():
            messagebox.showerror("Error", "Please select an output path!")
            return
            
        if not os.path.exists(self.image_folder.get()):
            messagebox.showerror("Error", "Input folder does not exist!")
            return
            
        self.is_processing = True
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        
        self.progress_bar['value'] = 0
        self.log_info("Starting video creation...")
        
        thread = threading.Thread(target=self.create_video_thread)
        thread.daemon = True
        thread.start()
        
    def create_video_thread(self):
        try:
            create_video_from_images(
                self.image_folder.get(),
                self.output_path.get(),
                self.duration_var.get(),
                self.fps_var.get(),
                self.update_progress
            )
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Video created successfully!\n\nSaved as: {self.output_path.get()}"))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.root.after(0, lambda: self.log_info(f"ERROR: {error_msg}"))
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            
        finally:
            self.root.after(0, self.reset_ui)
            
    def cancel_operation(self):
        self.is_processing = False
        self.log_info("Operation cancelled by user")
        self.reset_ui()
        
    def reset_ui(self):
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.progress_var.set("Ready to start...")
        self.progress_bar['value'] = 0
        
    def delete_temp_files(self):
        if not self.image_folder.get():
            messagebox.showwarning("Warning", "Please select an input folder first!")
            return
            
        folder_path = self.image_folder.get()
        temp_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('_temp.jpg'):
                    temp_files.append(os.path.join(root, file))
        
        if not temp_files:
            messagebox.showinfo("Info", "No temporary files found!")
            return
            
        result = messagebox.askyesno("Confirm", f"Found {len(temp_files)} temporary files. Delete them?")
        if result:
            deleted_count = 0
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        deleted_count += 1
                except Exception as e:
                    self.log_info(f"Failed to delete {temp_file}: {e}")
            
            self.log_info(f"Deleted {deleted_count} temporary files")
            messagebox.showinfo("Success", f"Deleted {deleted_count} temporary files!")

def main():
    parser = argparse.ArgumentParser(description="Create video from images in a folder")
    parser.add_argument("--folder", "-f", help="Input folder containing images")
    parser.add_argument("--output", "-o", help="Output video file path")
    parser.add_argument("--duration", "-d", type=float, default=2.0, help="Duration per image in seconds (default: 2.0)")
    parser.add_argument("--fps", type=int, default=24, help="Frames per second (default: 24)")
    parser.add_argument("--nogui", action="store_true", help="Run in command line mode without GUI")
    
    args = parser.parse_args()
    
    if not args.nogui:
        root = tk.Tk()
        app = VideoMakerGUI(root)
        root.mainloop()
        return
    
    try:
        if not args.folder:
            print("Error: Input folder is required in command line mode!")
            print("Use --folder to specify the input folder or remove --nogui to use GUI mode")
            return
            
        image_folder = args.folder
        
        if not os.path.exists(image_folder):
            print(f"Error: Folder '{image_folder}' does not exist!")
            return
            
        duration_per_image = args.duration
        
        if not args.output:
            output_path = os.path.join(image_folder, "output_video.mp4")
        else:
            output_path = args.output
            
        print(f"Input folder: {image_folder}")
        print(f"Output video: {output_path}")
        print(f"Duration per image: {duration_per_image} seconds")
        print(f"FPS: {args.fps}")
        
        def console_progress(message, progress):
            print(f"[{progress:5.1f}%] {message}")
        
        create_video_from_images(image_folder, output_path, duration_per_image, args.fps, console_progress)
        print("Video creation completed successfully!")
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)

if __name__ == "__main__":
    main()
