import requests
import base64
import json

with open("apis/ocrapi.json", "r", encoding='utf-8') as file:
    API_KEY = json.load(file)[0]

with open("apis/ocrapi.json", "r", encoding='utf-8') as file:
    FOLDER_ID = json.load(file)[1]


def analyze_test_image(image_path):
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()

        image_base64 = base64.b64encode(image_data).decode('utf-8')

        url = "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze"
        headers = {
            "Authorization": f"Api-Key {API_KEY}",
            "Content-Type": "application/json"
        }

        body = {
            "folderId": FOLDER_ID,
            "analyze_specs": [{
                "content": image_base64,
                "features": [{
                    "type": "TEXT_DETECTION",
                    "text_detection_config": {
                        "language_codes": ["*"]
                    }
                }]
            }]
        }

        response = requests.post(url, headers=headers, json=body)

        if response.status_code == 200:
            result = response.json()
            return extract_text(result)
        else:
            print(f"Ошибка API: {response.status_code}")
            print(f"Ответ: {response.text}")
            return None

    except Exception as e:
        print(f"Exception: {e}")
        return None


def extract_text(ocr_response):
    try:
        # Упрощенная и более надежная версия извлечения текста
        text_blocks = []

        # Получаем все страницы
        pages = ocr_response['results'][0]['results'][0]['textDetection']['pages']

        for page in pages:
            for block in page.get('blocks', []):
                for line in block.get('lines', []):
                    # Пробуем получить текст напрямую из линии
                    if line.get('text'):
                        text_blocks.append(line['text'].strip())
                    # Или собираем из слов
                    elif line.get('words'):
                        line_text = ' '.join(
                            word['text'] for word in line['words']
                            if word.get('text')
                        ).strip()
                        if line_text:
                            text_blocks.append(line_text)

        # Объединяем все текстовые блоки
        clean_text = '\n'.join(text_blocks)
        return clean_text if clean_text.strip() else "Текст не обнаружен"

    except Exception as e:
        print(f"Ошибка при извлечении текста: {e}")
        return None