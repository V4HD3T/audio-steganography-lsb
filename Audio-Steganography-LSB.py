import wave
import numpy as np
from PIL import Image


# Resmi bitlere d�n�şt�rme fonksiyonu
def image_to_bits(image_path):
    with Image.open(image_path) as img:
        img = img.convert('RGB')
        pixels = np.array(img)
        bits = []
        for pixel_row in pixels:
            for pixel in pixel_row:
                r, g, b = pixel
                bits.extend(format(r, '08b'))
                bits.extend(format(g, '08b'))
                bits.extend(format(b, '08b'))
        return bits


# Bitlerden resim oluşturma fonksiyonu
def bits_to_image(bits, image_size, output_path):
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
def hide_data_in_audio(audio_path, output_path, image_path):
    audio = wave.open(audio_path, mode='rb')
    frame_bytes = bytearray(list(audio.readframes(audio.getnframes())))

    image_bits = image_to_bits(image_path)
    image_size = Image.open(image_path).size

    width_bits = format(image_size[0], '016b')
    height_bits = format(image_size[1], '016b')
    size_bits = list(width_bits + height_bits)

    data_bits = size_bits + image_bits

    num_bits = len(data_bits)
    if num_bits > len(frame_bytes) * 4:  # LSB+2
        raise ValueError("Gizlenecek veri ses dosyasının kapasitesini aşıyor")

    for i, bit in enumerate(data_bits):
        # Her byte'ın 2. en az anlamlı bitini (LSB+2) image bit'i ile değiştir
        frame_bytes[i] = (frame_bytes[i] & 251) | (int(bit) << 2)

    frame_modified = bytes(frame_bytes)
    with wave.open(output_path, 'wb') as fd:
        fd.setparams(audio.getparams())
        fd.writeframes(frame_modified)

    audio.close()
    print("Gizli veri başarıyla saklandı")


# Ses dosyasından veri çıkarma fonksiyonu
def extract_bits_from_audio(audio_path):
    audio = wave.open(audio_path, mode='rb')
    frame_bytes = bytearray(list(audio.readframes(audio.getnframes())))

    size_bits = []
    for i in range(32):
        size_bits.append((frame_bytes[i] >> 2) & 1)

    width_bits = ''.join(map(str, size_bits[:16]))
    height_bits = ''.join(map(str, size_bits[16:]))

    width = int(width_bits, 2)
    height = int(height_bits, 2)
    image_size = (width, height)

    extracted_bits = []
    for i in range(32, 32 + width * height * 3 * 8):
        extracted_bits.append((frame_bytes[i] >> 2) & 1)

    audio.close()
    return extracted_bits, image_size


# SNR hesaplama fonksiyonu
def calculate_snr(original_audio, modified_audio):
    original_signal = np.frombuffer(original_audio.readframes(-1), dtype=np.int16)
    modified_signal = np.frombuffer(modified_audio.readframes(-1), dtype=np.int16)

    noise = original_signal - modified_signal
    noise_power = np.sum(noise ** 2)

    if noise_power == 0:
        return float('inf')  # Signal and noise are identical, return infinity

    signal_power = np.sum(original_signal ** 2)
    if signal_power == 0:
        return float('-inf')  # Signal power is zero, return negative infinity

    snr = 10 * np.log10(signal_power / noise_power)

    return snr


# ENG hesaplama fonksiyonu
def calculate_eng(original_audio, modified_audio):
    original_signal = np.frombuffer(original_audio.readframes(-1), dtype=np.int16)
    modified_signal = np.frombuffer(modified_audio.readframes(-1), dtype=np.int16)

    original_signal_power = np.sum(original_signal ** 2)
    noise_power = np.sum((original_signal - modified_signal) ** 2)

    if noise_power == 0:
        return float('inf')  # Signal and noise are identical, return infinity

    eng = original_signal_power / noise_power

    return eng


# Ana program fonksiyonu
def main():
    image_path = 'input_image.png'
    audio_input_path = 'input.wav'
    audio_output_path = 'output.wav'
    extracted_image_path = 'extracted_image.png'

    hide_data_in_audio(audio_input_path, audio_output_path, image_path)
    extracted_bits, image_size = extract_bits_from_audio(audio_output_path)
    bits_to_image(extracted_bits, image_size, extracted_image_path)

    with wave.open(audio_input_path, 'rb') as original_audio, wave.open(audio_output_path, 'rb') as modified_audio:
        snr_value = calculate_snr(original_audio, modified_audio)
        eng_value = calculate_eng(original_audio, modified_audio)
        if snr_value == float('inf'):
            print("SNR Değeri: Sonsuz (G�r�lt� Yok)")
        elif snr_value == float('-inf'):
            print("SNR Değeri: Tanımsız (Orijinal Sinyal Yok)")
        else:
            print(f"SNR Değeri: {snr_value:.2f} dB")
        print(f"ENG Değeri: {eng_value:.2f}")


if __name__ == '__main__':
    main()