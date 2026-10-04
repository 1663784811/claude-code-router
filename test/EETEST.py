from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = ""
)

completion = client.chat.completions.create(
  model="mistralai/mistral-nemotron",
  messages=[{"role":"user","content":"Write a limerick about the wonders of GPU computing."}],
  temperature=0.6,
  top_p=0.7,
  max_tokens=4096,
  stream=False
)

print(completion.choices[0].message)