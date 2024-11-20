import os
import sys
import uvicorn
import traceback

if __name__ == "__main__":
    try:
        # Change to the directory containing the script
        if getattr(sys, 'frozen', False):
            # If we're running as an executable
            application_path = os.path.dirname(sys.executable)
        else:
            # If we're running as a script
            application_path = os.path.dirname(os.path.abspath(__file__))
            
        os.chdir(application_path)
        print("Starting server...")
        
        # Run the server directly
        import main
        uvicorn.run(main.app, host="0.0.0.0", port=8000)
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        # Keep the window open
        input("\nPress Enter to exit...") 