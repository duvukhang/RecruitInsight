"""Deterministic multi-industry synthetic fixture; not observed market data."""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SECTORS = [
    ('Information Technology', ['Data Engineer', 'Backend Developer', 'Data Analyst'], 'python,sql,docker', 14000000),
    ('Finance', ['Financial Analyst', 'Kế toán tổng hợp', 'Chuyên viên tín dụng'], 'excel,accounting,analysis', 11000000),
    ('Marketing', ['Digital Marketing', 'Content Executive', 'Brand Specialist'], 'seo,content,analytics', 9000000),
    ('Logistics', ['Điều phối vận tải', 'Chuyên viên xuất nhập khẩu', 'Quản lý kho'], 'logistics,excel,planning', 9500000),
    ('Manufacturing', ['Kỹ sư sản xuất', 'Kỹ sư chất lượng', 'Kỹ thuật viên cơ khí'], 'autocad,quality,planning', 10500000),
    ('Retail', ['Quản lý cửa hàng', 'Nhân viên bán hàng', 'Chuyên viên mua hàng'], 'sales,communication,excel', 7500000),
    ('Education', ['Giáo viên tiếng Anh', 'Chuyên viên đào tạo', 'Tư vấn giáo dục'], 'english,teaching,communication', 9500000),
    ('Healthcare', ['Dược sĩ', 'Điều dưỡng', 'Nhân viên thiết bị y tế'], 'healthcare,communication,quality', 11000000),
    ('Construction', ['Kỹ sư xây dựng', 'Giám sát công trình', 'Kiến trúc sư'], 'autocad,planning,design', 12000000),
    ('Hospitality', ['Quản lý khách sạn', 'Nhân viên lễ tân', 'Điều hành tour'], 'english,service,communication', 8000000),
]
PROVINCES = ['Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng', 'Bình Dương', 'Đồng Nai', 'Hải Phòng', 'Cần Thơ', 'Bắc Ninh']


def generate(path, rows=50000, seed=2026):
    rng = random.Random(seed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ['source_job_id', 'job_title', 'company_name', 'province', 'industry', 'experience_years',
              'salary', 'salary_currency', 'posted_at', 'skills', 'remote_type', 'is_demo', 'dataset_origin']
    previous = None
    with path.open('w', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for i in range(rows):
            company = rng.randrange(240)
            industry, titles, skills, base = SECTORS[company % len(SECTORS)]
            experience = rng.randrange(13)
            province = rng.choice(PROVINCES)
            monthly = max(5000000, round((base + experience * 2100000 + (1500000 if province in PROVINCES[:2] else 0) + rng.gauss(0, 2200000)) / 100000) * 100000)
            row = {'source_job_id': f'DEMO-MULTI-{seed}-{i}', 'job_title': rng.choice(titles),
                   'company_name': f'DEMO Doanh nghiệp {company:03}', 'province': province, 'industry': industry,
                   'experience_years': experience, 'salary': f'{monthly} VND/tháng' if i % 6 else 'Negotiable',
                   'salary_currency': 'VND', 'posted_at': (date(2026, 1, 1) + timedelta(days=rng.randrange(270))).isoformat(),
                   'skills': skills, 'remote_type': rng.choice(['ONSITE', 'ONSITE', 'HYBRID', 'REMOTE']),
                   'is_demo': True, 'dataset_origin': 'synthetic'}
            if i % 97 == 0:
                row['job_title'] = ''
            if i % 113 == 0 and previous:
                row = dict(previous)
            writer.writerow(row)
            previous = row
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=50000)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--output', default='data/DEMO-multi-50k.csv')
    args = parser.parse_args()
    print(generate(args.output, args.rows, args.seed))
