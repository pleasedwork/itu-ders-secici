import requests
import json
from logger import Logger

class RequestManager:

    # The codes that indicate the operation was not successful but can be tried again.
    codes_to_try_again = [
        "VAL01",
        "VAL02",
        "VAL06",
        "VAL13",
        "VAL14",
        "VAL16",
        "ERRLoad",
        "NULLParam-CheckOgrenciKayitZamaniKontrolu",
        "Kontenjan Dolu",
    ]
    
    # Codes that indicate quota is full - should switch to backup CRN
    quota_full_codes = ["VAL06", "Kontenjan Dolu"]
    success_codes = ["successResult", "Ekleme İşlemi Başarılı", "Silme İşlemi Başarılı"]
    timeout_codes = ["VAL21"]
    
    # Source: https://github.com/MustafaKrc/ITU-CRN-Picker/blob/ffb2ca20c197092f54ade466439d890cd61acab6/core/crn_picker.py#L31
    return_values = {
        "successResult": "CRN {} için işlem başarıyla tamamlandı.",
        "errorResult": "CRN {} için Operasyon tamamlanamadı.",
        None: "CRN {} için Operasyon tamamlanamadı.",
        "error": "CRN {} için bir hata meydana geldi.",
        "VAL01": "CRN {} bir problemden dolayı alınamadı.",
        "VAL02": "CRN {} kayıt zaman engelinden dolayı alınamadı.",
        "VAL03": "CRN {} bu dönem zaten alındığından dolayı tekrar alınamadı.",
        "VAL04": "CRN {} ders planında yer almadığından dolayı alınamadı.",
        "VAL05": "CRN {} dönemlik maksimum kredi sınırını aştığından dolayı alınamadı.",
        "VAL06": "CRN {} kontenjan yetersizliğinden dolayı alınamadı.",
        "VAL07": "CRN {} daha önce AA notuyla verildiğinden dolayı alınamadı.",
        "VAL08": "CRN {} program şartını sağlamadığından dolayı alınamadı.",
        "VAL09": "CRN {} başka bir dersle çakıştığından dolayı alınamadı.",
        "VAL10": "CRN {} dersine kayıtlı olmadığınızdan dolayı hiç bir işlem yapılmadı.",
        "VAL11": "CRN {} önşartlardan dolayı alınamadı.",
        "VAL12": "CRN {} şu anki dönemde açılmadığından dolayı alınamadı.",
        "VAL13": "CRN {} geçici olarak engellenmiş olması sebebiyle alınamadı.",
        "VAL14": "Sistem geçici olarak yanıt vermiyor.",
        "VAL15": "Maksimum 12 CRN alabilirsiniz.",
        "VAL16": "Aktif bir işleminiz devam ettiğinden dolayı işlem yapılamadı.",
        "VAL18": "CRN {} engellendğinden dolayı alınamadı.",
        "VAL19": "CRN {} önlisans dersi olduğundan dolayı alınamadı.",
        "VAL20": "Dönem başına sadece 1 ders bırakabilirsiniz.",
        "CRNListEmpty": "CRN {} listesi boş göründüğünden alınamadı.",
        "CRNNotFound": "CRN {} bulunamadığından dolayı alınamadı.",
        "ERRLoad": "Sistem geçici olarak yanıt vermiyor.",
        "NULLParam-CheckOgrenciKayitZamaniKontrolu" : "CRN {} kayıt zaman engelinden dolayı alınamadı.",
        "Ekleme İşlemi Başarılı" : "CRN {} için ekleme işlemi başarıyla tamamlandı.",

        # Below are the codes that are not in the original source code.
        "Kontenjan Dolu" : "CRN {} için kontenjan dolu olduğundan dolayı alınamadı.",
        "Silme İşlemi Başarılı" : "CRN {} için silme işlemi başarıyla tamamlandı.",
        "VAL21": "İstek limitini aşıldığı için 1 saatlik ders seçim engeli yenildi.",
        "VAL22": "CRN {} daha önce CC ve üstü harf notu ile verildiği için yükseltmeye alınamaz."
    }

    def __init__(self, token, course_selection_url: str, course_time_check_url: str, backup_map: dict = None) -> None:
        """
        Args:
            token: String token or callable token getter function
            course_selection_url: Course selection API URL
            course_time_check_url: Time check API URL
            backup_map: Dictionary mapping primary CRN to list of backup CRNs or single backup CRN
        """
        self._token = token
        self._token_getter = token if callable(token) else None
        self.course_selection_url = course_selection_url
        self.course_time_check_url = course_time_check_url

        # Build alternative chains and active crns state
        self.alternative_chains = {}
        self.active_crns_state = {}

        backup_map = backup_map or {}
        for primary, backups in backup_map.items():
            if isinstance(backups, list):
                chain = [primary] + backups
            else:
                chain = [primary, backups]
            self.alternative_chains[primary] = chain
            self.active_crns_state[primary] = (primary, 0)

    def _get_current_token(self) -> str:
        """Returns the current token."""
        if self._token_getter:
            return self._token_getter()
        return self._token

    def _get_headers(self) -> dict[str, str]:
        return {
            'Authorization': self._get_current_token(),
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'
        }

    def check_course_selection_time(self) -> bool:
        response = requests.get(self.course_time_check_url, headers=self._get_headers())
        Logger.log(f"Zaman kontrol request response mesajı: {response.text}", silent=True)

        try:
            result_json = json.loads(response.text)
            enrollment_data = result_json["kayitZamanKontrolResult"]
            return enrollment_data["ogrenciSinifaKayitOlabilir"] or enrollment_data["ogrenciSiniftanAyrilabilir"]
        except Exception:
            # Sistem çöktüğünde böyle bir response dönüyor, bu yüzden JSON parse hatası alıyoruz. Bu çökme tam ders seçimi başladığında oluyor, o yüzden o durumda true döndür.
            # <DOCTYPE HTML kontrolü ile yapsak yeterli diğer durumda valid json döndürüyor ama değerler False oluyor.
            """
            <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN""http://www.w3.org/TR/html4/strict.dtd">

            <HTML><HEAD><TITLE>Service Unavailable</TITLE>

            <META HTTP-EQUIV="Content-Type" Content="text/html; charset=us-ascii"></HEAD>

            <BODY><h2>Service Unavailable</h2>

            <hr><p>HTTP Error 503. The service is unavailable.</p>

            </BODY></HTML>
            """
            if "<!DOCTYPE HTML" in response.text:
                Logger.log(f"Sistem çökmesi tespit edildi, ders seçimi için zaman uygun kabul ediliyor.\nkayitZamanKontrolResult:\n{response.text}", silent=True)
                return True
            return False

    def _swap_to_backup(self, crn: str, crn_list: list[str]) -> None:
        if crn in self.active_crns_state:
            chain_key, current_index = self.active_crns_state[crn]
            chain = self.alternative_chains[chain_key]
            next_index = (current_index + 1) % len(chain)
            next_crn = chain[next_index]

            if next_crn == chain_key:
                Logger.log(f"Yedek CRN {crn} başarısız oldu, asıl CRN olan {next_crn} tekrar denenecek...")
            else:
                Logger.log(f"CRN {crn} yerine sıradaki yedek CRN {next_crn} denenecek...")

            crn_list.remove(crn)
            crn_list.append(next_crn)

            self.active_crns_state.pop(crn, None)
            self.active_crns_state[next_crn] = (chain_key, next_index)
        else:
            Logger.log(f"CRN {crn} listeden çıkarılıyor...")
            crn_list.remove(crn)

    def request_course_selection(self, crn_list: list[str], scrn_list: list[str]) -> tuple[list[str], list[str], bool]:
        # Send the request to the server.
        response = requests.post(self.course_selection_url, headers=self._get_headers(), json={"ECRN": crn_list, "SCRN": scrn_list})
        Logger.log(f"Ders Seçim request response mesajı: {response.text}", silent=True)
        
        time_out_detected = False
        try:
            result_json = json.loads(response.text)

            # Log the results of crn_list and determine if it is to be retried.
            for crn_result in result_json["ecrnResultList"]:
                crn = crn_result["crn"]
                result_code = crn_result["resultCode"]

                Logger.log(RequestManager.return_values.get(result_code, f"CRN {{}} için bilinmeyen hata kodu: {result_code}").format(crn))
                
                is_retriable = result_code in RequestManager.codes_to_try_again
                # Use the backup only if the quota is full, other codes in the codes_to_try_again array are usually caused by timing problems etc.
                should_use_backup = result_code in RequestManager.quota_full_codes
                is_success = result_code in RequestManager.success_codes
                timed_out = result_code in RequestManager.timeout_codes
                has_backup = crn in self.active_crns_state
            
                if timed_out:
                    time_out_detected = True
                    return crn_list, scrn_list, time_out_detected
                elif is_success:
                    crn_list.remove(crn)
                    self.active_crns_state.pop(crn, None)
                elif is_retriable:
                    if should_use_backup and has_backup:
                        self._swap_to_backup(crn, crn_list)
                    else:
                        Logger.log(f"CRN {crn} tekrar denenecek...")
                else:
                    if has_backup:
                        self._swap_to_backup(crn, crn_list)
                    else:
                        Logger.log(f"CRN {crn} listeden çıkarılıyor...")
                        crn_list.remove(crn)

            # Log the results of scrn_list and determine if it is to be retried.
            for scrn_result in result_json["scrnResultList"]:
                crn = scrn_result["crn"]
                result_code = scrn_result["resultCode"]

                Logger.log(RequestManager.return_values.get(result_code, f"CRN {{}} için bilinmeyen hata kodu: {result_code}").format(crn))
                if result_code in RequestManager.codes_to_try_again:
                    Logger.log(f"CRN {crn} tekrar denenecek...")
                else:
                    scrn_list.remove(crn)
        except json.JSONDecodeError as e:
            Logger.log(f"CRN listesi işlenirken JSON hatası meydana geldi, request geçerli bir JSON döndürmedi: {e}", silent=True)
        except Exception as e:
            Logger.log(f"CRN listesi işlenirken bir hata meydana geldi: {e}", silent=True)
        finally:
            return crn_list, scrn_list, time_out_detected
