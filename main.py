import pandas as pd
import streamlit as st
from datetime import datetime

# ========== HÀM TÍNH ĐỀ XUẤT ==========
def tinh_de_xuat(row, use_existing=False):
    if use_existing and 'DeXuat_co_san' in row and pd.notna(row['DeXuat_co_san']):
        return max(0, row['DeXuat_co_san'])
    else:
        sltb = row['SLTB']
        ct = row['CT']
        ton = row['Ton']
        return max(0, (sltb * ct) - ton)

# ========== HÀM KIỂM TRA BẤT THƯỜNG ==========
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

# ========== HÀM LỌC PHI LOGIC (AI QUYẾT ĐỊNH) ==========
def loc_phi_logic(row, de_xuat):
    """
    Trả về (loai_bo, ly_do_loai_bo, de_xuat_sau_loc)
    """
    sltb = row['SLTB']
    ton = row['Ton']
    ct = row['CT']

    # Rule 1: Tồn cao, đề xuất thấp (ví dụ đề xuất < 5 và tồn > 10 ngày bán)
    if ton > 0 and sltb > 0:
        so_ngay_ban_duoc = ton / sltb
        if so_ngay_ban_duoc > 10 and de_xuat < 5:
            return True, f"Tồn {ton} đủ bán {so_ngay_ban_duoc:.1f} ngày, đề xuất {de_xuat} quá thấp", 0

    # Rule 2: Đề xuất cao nhưng bán thấp, tồn cao
    if de_xuat > 50 and sltb < 2 and ton > 50:
        return True, f"Đề xuất {de_xuat} cao, nhưng SLTB {sltb} thấp và tồn {ton} còn nhiều", 0

    # Rule 3: Bán thấp, tồn = 0 -> đặt một lượng tối thiểu = SLTB (hoặc SLTB * 2)
    if sltb < 5 and ton == 0:
        # Nếu đề xuất tính ra = 0 (do công thức), ta gán lại = sltb * 2
        if de_xuat == 0:
            de_xuat_moi = max(1, int(sltb * 2))
            return False, f"Bán thấp ({sltb}/ngày), tồn = 0 -> đặt tối thiểu {de_xuat_moi}", de_xuat_moi
        else:
            # Nếu đã có đề xuất > 0 thì giữ nguyên
            return False, "", de_xuat

    # Các trường hợp khác giữ nguyên
    return False, "", de_xuat

# ========== GIAO DIỆN ==========
st.set_page_config(page_title="AI Đặt Hàng Siêu Thị", layout="wide", initial_sidebar_state="expanded")
st.title("🛒 Trợ lý AI Đặt Hàng Siêu Thị")
st.markdown("Hệ thống tự động đề xuất, lọc phi logic và cảnh báo bất thường.")

ct_input = st.sidebar.number_input("Chu kỳ đặt hàng (ngày)", min_value=1, value=7, step=1, help="Số ngày trung bình giữa các lần đặt hàng")

uploaded_file = st.file_uploader("Tải lên file dữ liệu (CSV hoặc Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, skiprows=1)
        st.success(f"Đã đọc file thành công! Số dòng: {len(df)}")
        st.subheader("Dữ liệu đầu vào (10 dòng đầu)")
        st.dataframe(df.head(10))
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
        st.stop()

    # Ánh xạ cột
    required_cols = ['madathang', 'ten', 'Tồn B.Trường', 'SLTB B.Trường']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.error(f"Thiếu các cột bắt buộc: {missing}")
        st.info("Danh sách cột hiện tại: " + ", ".join(df.columns))
        st.stop()

    df.rename(columns={
        'madathang': 'SKU',
        'ten': 'TenSanPham',
        'Tồn B.Trường': 'Ton',
        'SLTB B.Trường': 'SLTB'
    }, inplace=True)

    co_de_xuat_co_san = 'SL PLT2 P.bổ cho B.trường' in df.columns
    if co_de_xuat_co_san:
        df.rename(columns={'SL PLT2 P.bổ cho B.trường': 'DeXuat_co_san'}, inplace=True)
        st.info("✅ Sử dụng cột đề xuất có sẵn.")
    else:
        st.warning("Không có cột đề xuất, sẽ tự tính.")

    # Lọc bỏ SLTB = 0
    df = df[df['SLTB'].notna() & (df['SLTB'] > 0)]
    if len(df) == 0:
        st.warning("Không có dữ liệu hợp lệ.")
        st.stop()

    df['CT'] = ct_input
    df['DeXuat'] = df.apply(lambda row: tinh_de_xuat(row, use_existing=co_de_xuat_co_san), axis=1)

    # ===== ÁP DỤNG LỌC PHI LOGIC =====
    df['LoaiBo'] = False
    df['LyDoLoaiBo'] = ""
    df['DeXuatSauLoc'] = 0
    for idx, row in df.iterrows():
        loai_bo, ly_do, de_xuat_moi = loc_phi_logic(row, row['DeXuat'])
        df.at[idx, 'LoaiBo'] = loai_bo
        df.at[idx, 'LyDoLoaiBo'] = ly_do
        df.at[idx, 'DeXuatSauLoc'] = de_xuat_moi if not loai_bo else 0

    # Tách nhóm
    df_bi_loai = df[df['LoaiBo']]
    df_khong_loai = df[~df['LoaiBo']]

    # Kiểm tra bất thường cho những sản phẩm không bị loại
    df_khong_loai['BatThuong'] = False
    df_khong_loai['LyDo'] = ""
    for idx, row in df_khong_loai.iterrows():
        de_xuat = row['DeXuatSauLoc']
        bat_thuong, ly_do = kiem_tra_bat_thuong(row, de_xuat)
        df_khong_loai.at[idx, 'BatThuong'] = bat_thuong
        df_khong_loai.at[idx, 'LyDo'] = ly_do

    df_hop_le = df_khong_loai[~df_khong_loai['BatThuong']]
    df_bat_thuong = df_khong_loai[df_khong_loai['BatThuong']]

    # Hiển thị danh sách bị loại (phi logic)
    st.markdown("---")
    st.subheader("🚫 Danh sách bị loại (phi logic - không đặt)")
    if len(df_bi_loai) > 0:
        st.dataframe(df_bi_loai[['SKU', 'TenSanPham', 'Ton', 'SLTB', 'DeXuat', 'LyDoLoaiBo']])
    else:
        st.success("Không có sản phẩm phi logic.")

    st.markdown("---")
    st.subheader("⚠️ Danh sách cần xác nhận (bất thường)")
    if len(df_bat_thuong) > 0:
        for idx, row in df_bat_thuong.iterrows():
            with st.expander(f"{row['TenSanPham']} (SKU: {row['SKU']})"):
                st.write(f"**Tồn kho:** {row['Ton']}")
                st.write(f"**SLTB:** {row['SLTB']} / ngày")
                st.write(f"**CT:** {row['CT']} ngày")
                st.write(f"**Đề xuất sau lọc:** {row['DeXuatSauLoc']}")
                st.warning(f"**Lý do bất thường:** {row['LyDo']}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Đồng ý đặt", key=f"ok_{idx}"):
                        st.session_state.setdefault('quyet_dinh', {})[row['SKU']] = ('DONG_Y', row['DeXuatSauLoc'])
                        st.success(f"Đồng ý đặt {row['DeXuatSauLoc']}")
                with col2:
                    if st.button("❌ Bỏ qua", key=f"skip_{idx}"):
                        st.session_state.setdefault('quyet_dinh', {})[row['SKU']] = ('BO_QUA', 0)
                        st.info("Đã bỏ qua")
                with col3:
                    so_luong_moi = st.number_input("Sửa số lượng", min_value=0, value=int(row['DeXuatSauLoc']), key=f"edit_{idx}")
                    if so_luong_moi != row['DeXuatSauLoc'] and st.button("Cập nhật", key=f"update_{idx}"):
                        st.session_state.setdefault('quyet_dinh', {})[row['SKU']] = ('SUA', so_luong_moi)
                        st.success(f"Cập nhật {so_luong_moi}")
    else:
        st.success("🎉 Không có bất thường.")

    st.markdown("---")
    st.subheader("✅ Danh sách tự động đặt (hợp lệ)")
    if len(df_hop_le) > 0:
        st.dataframe(df_hop_le[['SKU', 'TenSanPham', 'Ton', 'SLTB', 'CT', 'DeXuatSauLoc']])
    else:
        st.write("Không có sản phẩm tự động đặt.")

    # Tạo đơn hàng cuối cùng
    if st.button("📦 Tạo đơn hàng cuối cùng"):
        quyet_dinh = st.session_state.get('quyet_dinh', {})
        final_rows = []
        # Sản phẩm hợp lệ tự động
        for _, row in df_hop_le.iterrows():
            if row['DeXuatSauLoc'] > 0:
                final_rows.append({
                    'SKU': row['SKU'],
                    'TenSanPham': row['TenSanPham'],
                    'SoLuongDat': row['DeXuatSauLoc'],
                    'TrangThai': 'Tự động'
                })
        # Sản phẩm đã xác nhận
        for sku, (action, qty) in quyet_dinh.items():
            if action in ['DONG_Y', 'SUA'] and qty > 0:
                ten = df[df['SKU'] == sku]['TenSanPham'].values[0]
                final_rows.append({
                    'SKU': sku,
                    'TenSanPham': ten,
                    'SoLuongDat': qty,
                    'TrangThai': 'Đã xác nhận'
                })
        if final_rows:
            df_final = pd.DataFrame(final_rows)
            st.subheader("📋 Đơn hàng cuối cùng")
            st.dataframe(df_final)
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Tải đơn hàng CSV", csv, "don_hang.csv", "text/csv")
        else:
            st.warning("Không có sản phẩm để đặt.")
else:
    st.info("📂 Hãy tải lên file CSV hoặc Excel để bắt đầu.")
