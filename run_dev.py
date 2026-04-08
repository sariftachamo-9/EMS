import os
import sys
from app import create_app

def run_dev():
    # Set the Flask environment
    os.environ['FLASK_ENV'] = 'development'
    
    port = 5000

    # Ensure the port is free before starting (only on the first run, not in the reloader)
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        import subprocess
        try:
            # Kill any process on port 5000
            subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True)
            print(f"Cleaning up port {port}...")
        except Exception:
            pass

    # Initialize the Flask app
    app = create_app('development')
    
    # Try to use ngrok for public URL testing if installed
    # ONLY start ngrok in the main process, not the reloader child
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        try:
            from pyngrok import ngrok, conf
            from dotenv import load_dotenv
            
            load_dotenv() # Ensure .env is loaded so NGROK_AUTHTOKEN is available
            
            # Configure pyngrok to use the manually downloaded binary
            pyngrok_config = conf.PyngrokConfig(ngrok_path=".venv/bin/ngrok")
            
            # Open a ngrok tunnel to the dev server
            connect_kwargs = {"pyngrok_config": pyngrok_config}
            if os.environ.get('NGROK_DOMAIN'):
                connect_kwargs["domain"] = os.environ.get('NGROK_DOMAIN')
                
            tunnel = ngrok.connect(port, **connect_kwargs)
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
