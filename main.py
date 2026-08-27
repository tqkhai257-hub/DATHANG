import pandas as pd
import streamlit as st
from datetime import datetime

# ========== 1. Hàm tính toán đề xuất ==========
def tinh_de_xuat(row, use_existing=False):
    if use_existing and 'DeXuat_co_san' in row and pd.notna(row['DeXuat_co_san']):
        return max(0, row['DeXuat_co_san'])
    else:
        sltb = row['SLTB']
        ct = row['CT']
        ton = row['Ton']
        return max(0, (sltb * ct) - ton)

# ========== 2. Hàm kiểm tra bất thường ==========
def kiem_tra_bat_thuong(row, de_xuat):
    sltb = row['SLTB']
    ton = row['Ton']
    ct = row['CT']
    ly_do = []
    if sltb > 0:
        so_ngay_ban_duoc = ton / sltb
        if so_ngay_ban_duoc > 10:
            ly_do.append(f"Tồn kho {ton} đủ bán trong {so_ngay_ban_duoc:.1f} ngày (quá nhiều)")
    nhu_cau_toi_da = sltb * ct * 1.5
    if de_xuat > nhu_cau_toi_da:
        ly_do.append(f"Đề xuất {de_xuat} > {nhu_cau_toi_da:.1f} (vượt 1.5 lần nhu cầu thực)")
    return len(ly_do) > 0, "; ".join(ly_do)

# ========== 3. Giao diện ==========
st.set_page_config(page_title="AI Đặt Hàng Siêu Thị", layout="wide", initial_sidebar_state="expanded")
st.title("🛒 Trợ lý AI Đặt Hàng Siêu Thị")
st.markdown("Hệ thống tự động đề xuất số lượng đặt và cảnh báo khi có bất thường để bạn xác nhận.")

ct_input = st.sidebar.number_input("Chu kỳ đặt hàng (ngày)", min_value=1, value=7, step=1, help="Số ngày trung bình giữa các lần đặt hàng")

uploaded_file = st.file_uploader("Tải lên file dữ liệu (CSV hoặc Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # Đọc file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            # Bỏ qua dòng đầu tiên (dòng tiêu đề ngày)
            df = pd.read_excel(uploaded_file, skiprows=1)  # dòng thứ 2 sẽ là header
        st.success(f"Đã đọc file thành công! Số dòng: {len(df)}")
        st.subheader("Dữ liệu đầu vào (10 dòng đầu)")
        st.dataframe(df.head(10))
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
        st.stop()

    # ===== ÁNH XẠ CỘT =====
    # Kiểm tra các cột bắt buộc
    required_cols = ['madathang', 'ten', 'Tồn B.Trường', 'SLTB B.Trường']
    if not all(col in df.columns for col in required_cols):
        st.error(f"File không đúng định dạng. Cần có các cột: {', '.join(required_cols)}")
        st.info("Danh sách cột hiện tại: " + ", ".join(df.columns))
        st.stop()

    # Đổi tên
    df.rename(columns={
        'madathang': 'SKU',
        'ten': 'TenSanPham',
        'Tồn B.Trường': 'Ton',
        'SLTB B.Trường': 'SLTB'
    }, inplace=True)

    # Kiểm tra cột đề xuất có sẵn
    co_de_xuat_co_san = 'SL PLT2 P.bổ cho B.trường' in df.columns
    if co_de_xuat_co_san:
        df.rename(columns={'SL PLT2 P.bổ cho B.trường': 'DeXuat_co_san'}, inplace=True)
        st.info("✅ Sử dụng cột 'SL PLT2 P.bổ cho B.trường' làm đề xuất.")
    else:
        st.warning("Không tìm thấy cột đề xuất, sẽ tự động tính theo công thức (SLTB * CT - Tồn).")

    # Lọc bỏ dòng có SLTB = 0 hoặc NaN (không có nhu cầu)
    df = df[df['SLTB'].notna() & (df['SLTB'] > 0)]
    if len(df) == 0:
        st.warning("Không có dữ liệu hợp lệ (SLTB > 0). Hãy kiểm tra file.")
        st.stop()

    # Gán CT
    df['CT'] = ct_input

    # Tính đề xuất
    df['DeXuat'] = df.apply(lambda row: tinh_de_xuat(row, use_existing=co_de_xuat_co_san), axis=1)

    # Kiểm tra bất thường
    df['BatThuong'] = False
    df['LyDo'] = ""
    for idx, row in df.iterrows():
        bat_thuong, ly_do = kiem_tra_bat_thuong(row, row['DeXuat'])
        df.at[idx, 'BatThuong'] = bat_thuong
        df.at[idx, 'LyDo'] = ly_do

    # Tách nhóm
    df_hop_le = df[~df['BatThuong']]
    df_bat_thuong = df[df['BatThuong']]

    st.markdown("---")
    st.subheader("⚠️ Danh sách cần xác nhận (bất thường)")

    if len(df_bat_thuong) > 0:
        for idx, row in df_bat_thuong.iterrows():
            with st.expander(f"{row['TenSanPham']} (SKU: {row['SKU']})"):
                st.write(f"**Tồn kho:** {row['Ton']}")
                st.write(f"**SLTB:** {row['SLTB']} / ngày")
                st.write(f"**Chu kỳ (CT):** {row['CT']} ngày")
                st.write(f"**Đề xuất ban đầu:** {row['DeXuat']}")
                st.warning(f"**Lý do:** {row['LyDo']}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Đồng ý đặt", key=f"ok_{idx}"):
                        st.session_state.setdefault('quyet_dinh', {})[row['SKU']] = ('DONG_Y', row['DeXuat'])
                        st.success(f"Đã đồng ý đặt {row['DeXuat']} cho {row['TenSanPham']}")
                with col2:
                    if st.button("❌ Bỏ qua", key=f"skip_{idx}"):
                        st.session_state.setdefault('quyet_dinh', {})[row['SKU']] = ('BO_QUA', 0)
                        st.info(f"Đã bỏ qua {row['TenSanPham']}")
                with col3:
                    so_luong_moi = st.number_input("Sửa số lượng", min_value=0, value=int(row['DeXuat']), key=f"edit_{idx}")
                    if so_luong_moi != row['DeXuat'] and st.button("Cập nhật", key=f"update_{idx}"):
                        st.session_state.setdefault('quyet_dinh', {})[row['SKU']] = ('SUA', so_luong_moi)
                        st.success(f"Đã cập nhật số lượng {so_luong_moi}")
    else:
        st.success("🎉 Không có sản phẩm bất thường! Tất cả đều hợp lệ.")

    st.markdown("---")
    st.subheader("✅ Danh sách tự động đặt (hợp lệ)")
    if len(df_hop_le) > 0:
        st.dataframe(df_hop_le[['SKU', 'TenSanPham', 'Ton', 'SLTB', 'CT', 'DeXuat']])
    else:
        st.write("Không có sản phẩm tự động đặt.")

    # Nút tạo đơn hàng
    if st.button("📦 Tạo đơn hàng cuối cùng"):
        quyet_dinh = st.session_state.get('quyet_dinh', {})
        final_rows = []
        for _, row in df_hop_le.iterrows():
            if row['DeXuat'] > 0:
                final_rows.append({'SKU': row['SKU'], 'TenSanPham': row['TenSanPham'], 'SoLuongDat': row['DeXuat'], 'TrangThai': 'Tu dong'})
        for sku, (action, qty) in quyet_dinh.items():
            if action in ['DONG_Y', 'SUA'] and qty > 0:
                ten = df[df['SKU'] == sku]['TenSanPham'].values[0]
                final_rows.append({'SKU': sku, 'TenSanPham': ten, 'SoLuongDat': qty, 'TrangThai': 'Da xac nhan'})
        if final_rows:
            df_final = pd.DataFrame(final_rows)
            st.subheader("📋 Đơn hàng cuối cùng")
            st.dataframe(df_final)
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Tải đơn hàng CSV", csv, "don_hang.csv", "text/csv")
        else:
            st.warning("Không có sản phẩm nào để đặt.")
else:
    st.info("📂 Hãy tải lên file CSV hoặc Excel để bắt đầu.")
