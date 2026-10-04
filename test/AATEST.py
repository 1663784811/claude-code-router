from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = ""
)

completion = client.chat.completions.create(
  model="z-ai/glm-5.3",
  messages=[{"role":"system","content":"You are a helpful assistant."},{"role":"user","content":"你好"}],
  temperature=0.5,
  top_p=1,
  max_tokens=1024,
  stream=False
)

print("======")
print(completion.choices[0].message)

print("======")



