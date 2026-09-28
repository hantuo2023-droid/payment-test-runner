"""Normalize import syntax without rewriting credential contents."""
import csv
import re
import unicodedata


def fields(line, kind):
    line = line.strip().lstrip('\ufeff').strip()
    if kind == 'accounts':
        # Split only the first structural delimiter. Passwords may contain pipes,
        # commas, full-width characters or the other supported delimiter.
        match = re.match(r'^([^,|｜\t]+?)(?:----|[|｜\t])(.*)$', line)
        if match and not line.startswith('"'):
            return [match[1].strip(), match[2].strip()]
        return [x.strip() for x in next(csv.reader([line], strict=True, skipinitialspace=True))]
    # Numeric test data has no free-form credential fields. Normalize pasted
    # full-width digits/punctuation and invisible formatting characters here only.
    line = unicodedata.normalize('NFKC', line).translate({ord(c): None for c in '\ufeff\u200b\u200c\u200d\u2060'})
    if ',' in line or line.startswith('"'):
        return [x.strip() for x in next(csv.reader([line], strict=True, skipinitialspace=True))]
    for delimiter in ('|', '\t', ';', ':'):
        if delimiter in line:
            return [x.strip() for x in line.split(delimiter)]
    # Right splitting keeps spaces within a formatted card number intact.
    combined = re.match(r'^(.*?)\s+([0-9]{1,2}\s*/\s*[0-9]{2}(?:[0-9]{2})?)\s+([0-9]{3,4})$', line)
    if combined:
        return list(combined.groups())
    return line.rsplit(None, 3)


def header(parts, kind):
    normalized = tuple(x.strip().lower() for x in parts)
    return normalized in ({('email', 'password')} if kind == 'accounts' else {
        ('number', 'month', 'year', 'cvc'), ('number', 'expiry', 'cvc'),
    })


def card_fields(parts):
    if len(parts) == 3:
        expiry = re.fullmatch(r'([0-9]{1,2})\s*/\s*([0-9]{2}|[0-9]{4})', parts[1])
        if not expiry:
            raise ValueError('有效期需要 MM/YY 或 MM/YYYY')
        parts = [parts[0], expiry[1], expiry[2], parts[2]]
    if len(parts) != 4:
        raise ValueError('需要卡号、月份、年份、CVC；也支持卡号、MM/YY、CVC')
    pan = re.sub(r'[\s-]', '', parts[0])
    if not re.fullmatch(r'[0-9]{12,19}', pan):
        raise ValueError('需要 12–19 位官方测试卡号；仅用于授权非 Production 环境')
    month, year, cvc = parts[1:]
    if not re.fullmatch(r'[0-9]{1,2}', month) or not 1 <= int(month) <= 12:
        raise ValueError('月份需要 1–12')
    if not re.fullmatch(r'[0-9]{2}|[0-9]{4}', year) or (len(year) == 4 and int(year) < 1000):
        raise ValueError('年份需要两位 YY 或四位 YYYY')
    if not re.fullmatch(r'[0-9]{3,4}', cvc):
        raise ValueError('CVC 需要三位或四位数字')
    return {'number': pan, 'month': f'{int(month):02d}',
            'year': '20'+year if len(year) == 2 else year, 'cvc': cvc}
