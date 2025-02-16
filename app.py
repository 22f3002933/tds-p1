import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from dotenv import load_dotenv
import requests
import json
import subprocess   
import uuid

app = FastAPI()

load_dotenv()
LLM_BASE_URL="https://aiproxy.sanand.workers.dev/openai/v1"
LLM_API_KEY=os.getenv("AIPROXY_TOKEN")

async def execute_code(code_response):
    try:
        # Create temporary file for Python code
        if code_response["language"] == "python":
            temp_file_id = uuid.uuid4().hex
            temp_file = f"{temp_file_id}.py"

            # Create the file adn write the code
            with open(temp_file, "w") as f:
                f.write(code_response["code"])
            
            print(f"Executing Python code in file {temp_file}")

            # Execute Python code
            result = subprocess.run(
                ["uv", "run", f"{temp_file}"],
                capture_output=True,
                text=True,
                check=True
            )

            # Clean up
            os.remove(temp_file)
            
        else:  # Bash
            print("Executing Bash code")
            result = subprocess.run(
                code_response["code"],
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )

        return {
            "status": "success",
            "error": result.stderr,
            "output": result.stdout,
            "code": code_response["code"]
        }

    except subprocess.CalledProcessError as e: 
        if code_response["language"] == "python":
            # Retry with python3
            return await execute_python_code_via_python3(temp_file, code_response["code"])
        
        return {
            "status": "error",
            "error": f"Execution failed: {e.stderr}",
            "code": code_response["code"]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "code": code_response["code"]
        }


async def execute_python_code_via_python3(temp_file, code):
    try:        
        print(f"Executing Python code with python3 again in file {temp_file}")

        # Execute Python code
        result = subprocess.run(
            ["python3", f"{temp_file}"],
            capture_output=True,
            text=True,
            check=True
        )

        # Clean up
        os.remove(temp_file)
        
        return {
            "status": "success",
            "error": result.stderr,
            "output": result.stdout,
            "code": code
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "code": code
        }

async def get_llm_response(prompt):  
    try: 
        system_prompt_txt = open("./system_prompt.txt", "r")
        system_prompt = system_prompt_txt.read()

        #  read from "./response.json"
        structured_response_json = open("./structured_response.json", "r")
        structured_response = json.load(structured_response_json)

        response = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers= {
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system", 
                        "content": f"{system_prompt}"
                    
                    },
                    {"role": "user", "content": f"{prompt}"}
                ],
                "response_format": structured_response
            }
        )
        response.raise_for_status()

        message = response.json()["choices"][0]["message"]
        return message
    except Exception as e:
        raise

async def retry_with_error(task: str, error: str):
    try: 
            
        retry_prompt =f"""The previous attempt to solve this task failed with the following error: {error}

    Please generate a new solution that avoids this error.

    ORIGINAL TASK:
    {task}

    Remember all security constraints and requirements from before."""
        return await get_llm_response(retry_prompt)
    except Exception as e:
        raise

@app.post("/run")
async def run_task(task: str = Query(..., description="Plain-English task description")):
    try:

        # Get response from LLM
        print(task)
        print("Getting response from LLM")
        message = await get_llm_response(task)

        if message["refusal"]:
            print(f"Task refused by LLM: {message['refusal']}")
            return HTTPException(status_code=400, detail=f"Task refused by LLM: {message['refusal']}")
        
        output = json.loads(message["content"])
        if "refusal" in output["code"].lower():
            print(f"Task refused by LLM: {output['code']}")
            return HTTPException(status_code=400, detail=f"Task refused by LLM: {output['code']}")

        print(output)    

        print("Executing code")
        result = await execute_code(output)
        print(result)


        if result["status"] == "error":
            print("Task failed, retrying")
            retry_response = await retry_with_error(task, result["error"])
            output = retry_response["content"]
            print(output)
            result = await execute_code(json.loads(output))
        elif "error" in result['output'].lower() or "err" in result['error'].lower():
            print("Task failed, retrying")
            retry_response = await retry_with_error(task, result["output"])
            output = retry_response["content"]
            result = await execute_code(json.loads(output))
 
        if result["status"] == "error" or  "error" in result['output'].lower() or  "err" in result['error'].lower():
            print("Task failed after retry")
            return HTTPException(status_code=500, detail=f"Task failed: {result['error']}")

        return result
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": str(e)}

@app.get("/read")
def run_task(path: str = Query(..., description="Plain-English task description")):
    try:
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check that path should only access the file in the data directory, otherwise send 403
        if not "data" in path:
            raise HTTPException(status_code=403, detail="Forbidden")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        return PlainTextResponse(content, status_code=200)
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
