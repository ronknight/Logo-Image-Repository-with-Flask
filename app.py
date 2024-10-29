from flask import Flask, request, send_file, jsonify, render_template, redirect, url_for
from PIL import Image
from tinydb import TinyDB, Query
import os
from io import BytesIO

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/images'
db = TinyDB('image_catalog.json')

# Helper function to extract brand from filename
def extract_brand_from_filename(filename):
    name_part = os.path.splitext(filename)[0]
    brand = name_part.split('-logo')[0].split('_logo')[0]
    return brand.lower()

# Sync existing images in static/images folder with the database
def sync_images_with_db():
    existing_files = {item['filename'] for item in db.all()}
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(file_path) and filename not in existing_files:
            # Get image dimensions
            with Image.open(file_path) as img:
                width, height = img.size
            brand = extract_brand_from_filename(filename)
            db.insert({"brand": brand, "filename": filename, "width": width, "height": height})
            print(f"Added {filename} to the database with brand {brand} and dimensions {width}x{height}")

# Run sync on startup
sync_images_with_db()

# Route to upload images
@app.route('/upload_image', methods=['POST'])
def upload_image():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "File is required"}), 400

    filename = file.filename
    brand = extract_brand_from_filename(filename)

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # Get image dimensions
    with Image.open(file_path) as img:
        width, height = img.size

    # Insert image metadata into the database
    db.insert({"brand": brand, "filename": filename, "width": width, "height": height})
    return jsonify({"message": "Image uploaded successfully", "brand": brand, "filename": filename, "width": width, "height": height}), 200

# Route to display images in the gallery
@app.route('/')
def index():
    images = db.all()
    brands = {}
    for image in images:
        brand = image['brand']
        if brand not in brands:
            brands[brand] = []
        brands[brand].append({
            "filename": image['filename'],
            "width": image['width'],
            "height": image['height']
        })
    return render_template('index.html', brands=brands)

# Route to serve images with optional resizing and thumbnail support
@app.route('/images/<filename>')
def serve_image(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Image not found"}), 404

    # Check if thumbnail is requested
    is_thumbnail = request.args.get('thumbnail', 'false').lower() == 'true'
    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    # Open the image and resize if necessary
    image = Image.open(file_path)

    # Resize for thumbnail or to specified width and height
    if is_thumbnail:
        # Set a fixed thumbnail width, maintaining aspect ratio
        thumbnail_width = 150
        image.thumbnail((thumbnail_width, image.height), Image.LANCZOS)
    elif width or height:
        # Resize based on width or height if specified
        image.thumbnail((width or image.width, height or image.height))

    img_io = BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

# Route to delete an image
@app.route('/delete_image/<filename>', methods=['DELETE'])
def delete_image(filename):
    ImageQuery = Query()
    result = db.search(ImageQuery.filename == filename)
    if not result:
        return jsonify({"error": "Image not found"}), 404

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.remove(ImageQuery.filename == filename)
    return jsonify({"message": "Image deleted successfully"}), 200

# Route for drag-and-drop upload page
@app.route('/upload')
def upload():
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
