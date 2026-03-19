import hmac
import hashlib
import json
from datetime import datetime
import requests
from .base import BaseMiner

class AmazonMiner(BaseMiner):
    """Miner for Amazon Product Advertising API (PA-API 5.0)."""
    
    def run(self):
        cfg = self.config["marketplaces"].get("Amazon", {})
        if not cfg.get("active"):
            return

        access_key = cfg.get("access_key", "").strip()
        secret_key = cfg.get("secret_key", "").strip()
        associate_tag = cfg.get("tag", "").strip()
        keyword = cfg.get("keyword", "").strip()
        qtd = self.config.get("qtd_produtos", 5)

        if not (access_key and secret_key and associate_tag and keyword):
            self.log("❌ Amazon: Credenciais (Access Key, Secret Key, Tag) ou Palavra-chave ausentes.")
            return

        self.log(f"Buscando '{keyword}' na Amazon via API...")
        
        try:
            results = self._search_amazon(access_key, secret_key, associate_tag, keyword, qtd)
            
            if not results:
                self.log("⚠️ Nenhum produto encontrado na Amazon.")
                return

            for i, item in enumerate(results):
                if self.check_stop():
                    break
                
                # Report result and progress
                self.log_queue.put({"type": "result", "result": item})
                self.log(f"Item {i+1}/{len(results)} coletado", progress=(i + 1) / len(results))

        except Exception as e:
            self.log(f"❌ Erro na Amazon API: {str(e)[:150]}")

    def _search_amazon(self, access_key, secret_key, associate_tag, keyword, qtd):
        """Internal method to call PA-API 5.0 SearchItems."""
        host = "webservices.amazon.com.br"
        region = "us-east-1"
        service = "ProductAdvertisingAPI"
        target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
        url = f"https://{host}/paapi5/searchitems"

        # Payload
        payload = {
            "Keywords": keyword,
            "Resources": [
                "ItemInfo.Title",
                "Offers.Listings.Price"
            ],
            "PartnerTag": associate_tag,
            "PartnerType": "Associates",
            "Marketplace": "www.amazon.com.br",
            "ItemCount": min(qtd, 10) # API limit per request is 10
        }
        
        payload_str = json.dumps(payload)
        
        # Datetime for headers
        t = datetime.utcnow()
        amz_date = t.strftime('%Y%m%dT%H%M%SZ')
        datestamp = t.strftime('%Y%m%d')

        # 1. Canonical Request
        canonical_uri = '/paapi5/searchitems'
        canonical_querystring = ''
        canonical_headers = (
            f'content-encoding:amz-1.0\n'
            f'content-type:application/json; charset=utf-8\n'
            f'host:{host}\n'
            f'x-amz-date:{amz_date}\n'
            f'x-amz-target:{target}\n'
        )
        signed_headers = 'content-encoding;content-type;host;x-amz-date;x-amz-target'
        payload_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
        
        canonical_request = (
            f'POST\n{canonical_uri}\n{canonical_querystring}\n'
            f'{canonical_headers}\n{signed_headers}\n{payload_hash}'
        )

        # 2. String to Sign
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f'{datestamp}/{region}/{service}/aws4_request'
        string_to_sign = (
            f'{algorithm}\n{amz_date}\n{credential_scope}\n'
            + hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        )

        # 3. Signature
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

        def get_signature_key(key, date_stamp, region_name, service_name):
            k_date = sign(('AWS4' + key).encode('utf-8'), date_stamp)
            k_region = sign(k_date, region_name)
            k_service = sign(k_region, service_name)
            k_signing = sign(k_service, 'aws4_request')
            return k_signing

        signing_key = get_signature_key(secret_key, datestamp, region, service)
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # 4. Authorization Header
        authorization_header = (
            f'{algorithm} Credential={access_key}/{credential_scope}, '
            f'SignedHeaders={signed_headers}, Signature={signature}'
        )

        # Headers
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Content-Encoding': 'amz-1.0',
            'X-Amz-Date': amz_date,
            'X-Amz-Target': target,
            'Authorization': authorization_header
        }

        # Request
        response = requests.post(url, data=payload_str, headers=headers, timeout=30)
        
        if response.status_code != 200:
            try:
                err_data = response.json()
                err_msg = err_data.get("Errors", [{}])[0].get("Message", response.text)
            except:
                err_msg = response.text
            raise Exception(f"API returned {response.status_code}: {err_msg}")

        data = response.json()
        items = data.get("SearchResult", {}).get("Items", [])
        
        results = []
        for item in items:
            url_prod = item.get("DetailPageURL")
            results.append({
                "marketplace": "Amazon",
                "link_produto": url_prod,
                "link_afiliado": url_prod # PA-API link already includes the tag
            })
            
        return results
