# test_new_prompts.py - Скрипт для тестирования новых промптов

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.llm.gemini_client import (
    test_detect_intent_simple,
    test_parse_task_simple, 
    test_parse_reminder_time_simple,
    test_complete_task_flow,
    run_all_tests,
    test_intent_only,
    test_parsing_only,
    test_time_parsing_only
)

async def quick_test():
    """Быстрый тест нескольких примеров."""
    print("⚡ БЫСТРЫЙ ТЕСТ НОВЫХ ПРОМПТОВ")
    print("=" * 40)
    
    test_cases = [
        "купить молоко завтра",
        "напомни вечером воскресенья про встречу в понедельник в 10:00",
        "сделать презентацию к пятнице"
    ]
    
    for text in test_cases:
        await test_complete_task_flow(text)

async def interactive_test():
    """Интерактивный тест - пользователь вводит текст."""
    print("🎮 ИНТЕРАКТИВНЫЙ ТЕСТ")
    print("Введите текст для тестирования (или 'quit' для выхода):")
    
    while True:
        user_input = input("\n> ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
            
        if not user_input:
            continue
            
        # Спрашиваем, это реплай или нет
        is_reply_input = input("Это ответ на сообщение бота? (y/n): ").strip().lower()
        is_reply = is_reply_input in ['y', 'yes', 'да']
        
        await test_complete_task_flow(user_input, is_reply)

async def main():
    """Главная функция с меню."""
    print("🧪 ТЕСТИРОВАНИЕ НОВЫХ ПРОМПТОВ")
    print("Выберите тип теста:")
    print("1. Быстрый тест (несколько примеров)")
    print("2. Полный тест (все тестовые кейсы)")
    print("3. Только интенты")
    print("4. Только парсинг задач")  
    print("5. Только парсинг времени")
    print("6. Интерактивный тест")
    print("q. Выход")
    
    choice = input("\nВыберите опцию: ").strip()
    
    if choice == '1':
        await quick_test()
    elif choice == '2':
        await run_all_tests()
    elif choice == '3':
        await test_intent_only()
    elif choice == '4':
        await test_parsing_only()
    elif choice == '5':
        await test_time_parsing_only()
    elif choice == '6':
        await interactive_test()
    elif choice.lower() == 'q':
        print("Выход...")
        return
    else:
        print("Неверный выбор")
        await main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
    except Exception as e:
        print(f"\nОшибка при тестировании: {e}")
        import traceback
        traceback.print_exc()