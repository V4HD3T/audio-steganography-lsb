import wave
from PIL import Image
import numpy as np


# Resmi bitlere dönüştürme fonksiyonu
def image_to_bits(image_path):
    """
    Verilen resim dosyasını bitlere dönüştürür.
    """
    with Image.open(image_path) as img:
        img = img.convert('RGB')
        pixels = np.array(img)
        bits = []
        for pixel_row in pixels:
            for pixel in pixel_row:
                r, g, b = pixel
                # Her pikselin R, G ve B bileşenlerini 8 bit olarak sakla
                bits.extend(format(r, '08b'))
                bits.extend(format(g, '08b'))
                bits.extend(format(b, '08b'))
        return bits


# Bitlerden resim oluşturma fonksiyonu
def bits_to_image(bits, image_size, output_path):
    """
    Bitleri kullanarak bir resim oluşturur ve kaydeder.
    """
    bits = ''.join(map(str, bits))
    pixel_values = []
    for i in range(0, len(bits), 8):
        byte = bits[i:i + 8]
        pixel_values.append(int(byte, 2))

    pixel_array = np.array(pixel_values, dtype=np.uint8)
    pixel_array = pixel_array.reshape((image_size[1], image_size[0], 3))

    img = Image.fromarray(pixel_array, 'RGB')
    img.save(output_path)
    print(f"Gizli resim {output_path} dosyasına kaydedildi.")


# Ses dosyasına veri gizleme fonksiyonu
def hide_data_in_audio(audio_path, output_path, image_bits):
    """
    Verilen ses dosyasına bitleri gizler.
    """
    audio = wave.open(audio_path, mode='rb')
    frame_bytes = bytearray(list(audio.readframes(audio.getnframes())))

    num_bits = len(image_bits)
    if num_bits > len(frame_bytes) * 8:
        raise ValueError("Gizlenecek veri ses dosyasının kapasitesini aşıyor")

    for i, bit in enumerate(image_bits):
        # Her byte'ın en az anlamlı bitini (LSB) image bit'i ile değiştir
        frame_bytes[i] = (frame_bytes[i] & 254) | int(bit)

    frame_modified = bytes(frame_bytes)
    with wave.open(output_path, 'wb') as fd:
        fd.setparams(audio.getparams())
        fd.writeframes(frame_modified)

    audio.close()
    print("Gizli veri başarıyla saklandı")


# Ses dosyasından veri çıkarma fonksiyonu
def extract_bits_from_audio(audio_path, num_bits):
    """
    Ses dosyasından bitleri çıkarır.
    """
    audio = wave.open(audio_path, mode='rb')
    frame_bytes = bytearray(list(audio.readframes(audio.getnframes())))

    extracted_bits = []
    for i in range(num_bits):
        # Her byte'ın en az anlamlı bitini (LSB) oku
        extracted_bits.append(frame_bytes[i] & 1)

    audio.close()
    return extracted_bits


# Resmin boyutlarını belirleme fonksiyonu
def get_image_size(image_path):
    """
    Resmin boyutlarını döndürür.
    """
    with Image.open(image_path) as img:
        return img.size


# Ana program fonksiyonu
def main():
    """
    Ana program fonksiyonu.
    """
    # Resim dosyasının yolunu belirle
    image_path = 'input_image.png'

    # Ses dosyasının yolunu belirle
    audio_input_path = 'input.wav'
    audio_output_path = 'output.wav'

    # Gizli resmin çıkartılacağı yol
    extracted_image_path = 'extracted_image.png'

    # Resmin boyutlarını al
    image_size = get_image_size(image_path)

    # Resmi bitlere dönüştür
    image_bits = image_to_bits(image_path)

    # Ses dosyasına veriyi gizle
    hide_data_in_audio(audio_input_path, audio_output_path, image_bits)

    # Gizlenen bit sayısını belirle
    num_bits = len(image_bits)

    # Ses dosyasından bitleri çıkar
    extracted_bits = extract_bits_from_audio(audio_output_path, num_bits)

    # Çıkarılan bitleri bir resme dönüştür
    bits_to_image(extracted_bits, image_size, extracted_image_path)


# Ana programı çalıştır
if __name__ == '__main__':
    main()