from flask import Flask, render_template, request, send_file, redirect, url_for
import os
import io
import zipfile
import shutil
from werkzeug.utils import secure_filename
from functions.posterize_funcs import posterize_main

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------
# Routes
# ------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if 'image_file' not in request.files:
            return "No file part", 400
        file = request.files['image_file']
        if file.filename == '':
            return "No selected file", 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Collect user inputs
            tiling = int(request.form.get("tiling"))  # e.g., "1", "2", "4", "6"
            paper_size = request.form.get("paper_size")
            blurring = int(request.form.get("blurring"))
            layers = int(request.form.get("layers"))

            # Call posterize workflow
            output_folder = "posterized_variations"
            if os.path.exists(output_folder):
                shutil.rmtree(output_folder)

            posterize_main(filepath, layers, tiling, paper_size, blurring)

            # Zip up all generated PDFs and send as download
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(output_folder):
                    for f in files:
                        if f.endswith(".pdf"):
                            full_path = os.path.join(root, f)
                            arcname = os.path.relpath(full_path, output_folder)
                            zf.write(full_path, arcname)
            zip_buffer.seek(0)

            base_name = os.path.splitext(filename)[0]
            return send_file(
                zip_buffer,
                mimetype="application/zip",
                as_attachment=True,
                download_name=f"{base_name}_stencils.zip"
            )

    return render_template("home_page.html")


if __name__ == "__main__":
    app.run(debug=True)