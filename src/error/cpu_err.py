def cpu_err(e: Exception):
    print("Something went wrong during 'CPU' discovery.")
    print(
        "This should not happen. Please open an issue at https://github.com/iabtw/OCSysInfo/issues\n")
    print(f"Error logs:\n\n{str(e)}")
    exit(0)