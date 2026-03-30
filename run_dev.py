import os
import sys
from app import create_app

def run_dev():
    # Set the Flask environment
    os.environ['FLASK_ENV'] = 'development'
    
    # Initialize the Flask app
    app = create_app('development')
    
    port = 5000
    
    # Try to use ngrok for public URL testing if installed
    try:
        from pyngrok import ngrok
        # Open a ngrok tunnel to the dev server
        tunnel = ngrok.connect(port)
        public_url = tunnel.public_url
        os.environ['EXTERNAL_URL'] = public_url
        
        print("\n" + "="*50)
        print("EMS Development Server with Ngrok")
        print(f"Localhost URL: \033[94mhttp://127.0.0.1:{port}\033[0m")
        print(f"Ngrok Public URL: \033[92m{public_url}\033[0m")
        print("="*50 + "\n")
        
    except ImportError:
        print("\n[INFO] pyngrok not installed. Running without public tunnel.")
    except Exception as e:
        print(f"\n[WARNING] Could not start ngrok: {e}")
    
    # Start the app
    app.run(host='127.0.0.1', port=port, debug=True)

if __name__ == '__main__':
    run_dev()
