from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = ""
)

completion = client.chat.completions.create(
  model="z-ai/glm-5.3-flash",
  messages=[{"role":"user","content":"您好，请用中文回答我"}],
  temperature=1,
  top_p=0.95,
  max_tokens=8192,
  stream=False
)


print(completion.choices[0].message)