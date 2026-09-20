import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from . import prompts, tools

load_dotenv()

class NutritionAgent:
    def __init__(self):
        # Используем Groq API, который полностью совместим с OpenAI SDK
        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url="https://api.groq.com/openai/v1"  # Адрес серверов Groq
        )
        self.messages = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT}
        ]
        # Словарь доступных инструментов
        self.available_tools = {
            "calculate_macros": tools.calculate_macros,
            "create_fitness_plan": tools.create_fitness_plan
        }

    def process_input(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        
        try:
            response = self.client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=self.messages,
                tools=tools.TOOLS_SCHEMA,
                tool_choice="auto",
                max_tokens=4096  # ✅ Увеличиваем лимит ответа
            )
            
            response_message = response.choices[0].message
            self.messages.append(response_message)

            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    if tool_name in self.available_tools:
                        tool_result = self.available_tools[tool_name](**tool_args)
                        
                        self.messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })
                
                final_response = self.client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=self.messages,
                    max_tokens=4096  # ✅ Увеличиваем лимит ответа
                )
                final_message = final_response.choices[0].message.content
                self.messages.append({"role": "assistant", "content": final_message})
                return final_message
            else:
                return response_message.content

        except Exception as e:
            return f"Произошла ошибка при обращении к модели: {str(e)}"