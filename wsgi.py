from app import create_app
import os

# Create the application instance using the production configuration
app = create_app('production')

if __name__ == "__main__":
    # This is for testing the WSGI entry point locally if needed
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
