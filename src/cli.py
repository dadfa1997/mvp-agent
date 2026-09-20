from .agent import NutritionAgent

def main():
    print("👋 Привет! Я агент для расчёта нормы калорий и БЖУ.")
    print("Напиши мне свои параметры (пол, возраст, вес, рост, активность) или просто задай вопрос.")
    print("Для выхода введи 'exit' или 'quit'.\n")
    
    agent = NutritionAgent()
    
    while True:
        try:
            user_input = input("Вы: ").strip()
            if user_input.lower() in ['exit', 'quit', 'выход']:
                print("До свидания!")
                break
            if not user_input:
                continue
                
            response = agent.process_input(user_input)
            print(f"\nАгент: {response}\n")
            
        except KeyboardInterrupt:
            print("\nДо свидания!")
            break
        except Exception as e:
            print(f"\nНепредвиденная ошибка: {e}\n")

if __name__ == "__main__":
    main()