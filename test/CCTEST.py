from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)

completion = client.chat.completions.create(
  model="meta/muse-glimmer-30b",
  messages=[{"role":"user","content":"您好，请用中文回答我"}],
  temperature=1,
  top_p=0.95,
  max_tokens=8192,
  stream=False
)

print(completion.choices[0].message.content)