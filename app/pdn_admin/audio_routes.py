import logging
import os
from flask import Blueprint, request, jsonify, send_file, Response
from werkzeug.exceptions import RequestedRangeNotSatisfiable

from ..utils.pdn_file_path import PDNFilePath

logger = logging.getLogger(__name__)

audio_bp = Blueprint('audio', __name__)


@audio_bp.route('/audio/<path:filename>')
def serve_audio(filename):
    """
    Serve audio files with proper range request handling
    """
    try:
        # Decode the URL-encoded filename
        import urllib.parse
        decoded_filename = urllib.parse.unquote(filename)

        # The filename format is: useremail/filename.wav
        # Split to get user directory and actual filename
        if '/' in decoded_filename:
            user_part, actual_filename = decoded_filename.split('/', 1)
        else:
            # Fallback if no user directory in path
            user_part = "default"
            actual_filename = decoded_filename

        # Get the user directory
        pdn_file_path = PDNFilePath()
        user_dir = pdn_file_path.get_user_dir(user_part)

        # Construct the full file path
        file_path = user_dir / actual_filename

        # Check if file exists
        if not file_path.exists():
            logger.error(f"Audio file not found: {file_path}")
            return jsonify({"error": "Audio file not found"}), 404

        # Get file size
        file_size = os.path.getsize(file_path)

        # Handle empty files
        if file_size == 0:
            logger.warning(f"Audio file is empty: {file_path}")
            return jsonify({"error": "Audio file is empty"}), 404

        # Handle range requests
        range_header = request.headers.get('Range', None)

        if range_header:
            try:
                # Parse range header (e.g., "bytes=0-1023")
                range_str = range_header.replace('bytes=', '')
                start, end = range_str.split('-')
                start = int(start)
                end = int(end) if end else file_size - 1

                # Validate range
                if start >= file_size or end >= file_size or start > end:
                    raise RequestedRangeNotSatisfiable()

                # Read the requested range
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    data = f.read(end - start + 1)

                # Create response with range headers
                response = Response(data, 206, mimetype='audio/wav')
                response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
                response.headers.add('Accept-Ranges', 'bytes')
                response.headers.add('Content-Length', str(end - start + 1))
                return response

            except (ValueError, RequestedRangeNotSatisfiable):
                logger.error(f"Invalid range request: {range_header}")
                return jsonify({"error": "Invalid range request"}), 416

        # Serve full file if no range request
        return send_file(
            file_path,
            mimetype='audio/wav',
            as_attachment=False,
            download_name=actual_filename
        )

    except Exception as e:
        logger.error(f"Error serving audio file {filename}: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
