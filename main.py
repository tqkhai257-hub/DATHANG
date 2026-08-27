import pandas as pd
import streamlit as st

# ========== HÀM TÍNH ĐỀ XUẤT (có ràng buộc tồn PLT) ==========
def tinh_de_xuat(sltb, ct, ton, ton_plt, de_xuat_co_san=None):
    # Tính nhu cầu dựa trên SLTB và chu kỳ
    nhu_cau = max(0, (sltb * ct) - ton)
    
    # Nếu có đề xuất có sẵn (cột E) thì ưu tiên dùng, nhưng vẫn kiểm tra giới hạn
    if de_xuat_co_san is not None and pd.notna(de_xuat_co_san) and de_xuat_co_san > 0:
        de_xuat = max(0, de_xuat_co_san)
    else:
        de_xuat = nhu_cau
    
    # Ràng buộc: không vượt quá tồn PLT
    if de_xuat > ton_plt:
        de_xuat = ton_plt
    return de_xuat

# ========== HÀM KIỂM TRA BẤT THƯỜNG ==========
def kiem_tra_bat_thuong(sltb, ton, ct, de_xuat, ton_plt):
    ly_do = []
    # 1. Tồn tại cửa hàng quá nhiều
    if sltb > 0:
        so_ngay_ban_duoc = ton / sltb
        if so_ngay_ban_duoc > 10:
            ly_do.append(f"Tồn {ton} đủ bán {so_ngay_ban_duoc:.1f} ngày")
    # 2. Đề xuất vượt quá tồn PLT
    if de_xuat > ton_plt:
        ly_do.append(f"Đề xuất {de_xuat} vượt tồn PLT {ton_plt}")
    # 3. Đề xuất quá cao so với nhu cầu thực tế
    nhu_cau_toi_da = sltb * ct * 1.5
    if de_xuat > nhu_cau_toi_da:
        ly_do.append(f"Đề xuất {de_xuat} > {nhu_cau_toi_da:.1f} (vượt 1.5 lần nhu cầu)")
    return len(ly_do) > 0, "; ".join(ly_do)

# ========== LỌC PHI LOGIC ==========
def loc_phi_logic(sltb, ton, de_xuat, ton_plt):
    # Rule 1: Tồn cửa hàng cao, đề xuất thấp
    if ton > 0 and sltb > 0:
        so_ngay_ban_duoc = ton / sltb
        if so_ngay_ban_duoc > 10 and de_xuat < 5:
            return True, f"Tồn {ton} đủ bán {so_ngay_ban_duoc:.1f} ngày, đề xuất {de_xuat} quá thấp", 0
    # Rule 2: Đề xuất cao nhưng bán chậm, tồn cửa hàng nhiều
    if de_xuat > 50 and sltb < 2 and ton > 50:
        return True, f"Đề xuất {de_xuat} cao, SLTB {sltb} thấp, tồn {ton} còn nhiều", 0
    # Rule 3: Bán thấp nhưng tồn cửa hàng = 0 -> đặt tối thiểu
    if sltb < 5 and ton == 0:
        if de_xuat == 0:
            de_xuat_moi = max(1, int(sltb * 2))
            return False, f"Bán thấp ({sltb}/ngày), tồn=0 -> đặt tối thiểu {de_xuat_moi}", de_xuat_moi
        else:
            return False, "", de_xuat
    # Rule 4: Tồn PLT không đủ để đáp ứng đề xuất (cảnh báo nhưng không loại bỏ)
    if de_xuat > ton_plt:
        return False, f"Tồn PLT chỉ có {ton_plt}, đề xuất {de_xuat} bị giới hạn", ton_plt
    return False, "", de_xuat

# ========== GIAO DIỆN ==========
st.set_page_config(page_title="AI Đặt Hàng Siêu Thị", layout="wide")
st.title("🛒 Trợ lý AI Đặt Hàng Siêu Thị")
st.markdown("Hệ thống tự động đề xuất, lọc phi logic và cảnh báo bất thường.")

ct_input = st.sidebar.number_input("Chu kỳ đặt hàng (ngày)", min_value=1, value=7, step=1)

uploaded_file = st.file_uploader("Tải lên file dữ liệu (CSV hoặc Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=2, header=None)
        else:
            df = pd.read_excel(uploaded_file, skiprows=2, header=None)
        st.success(f"Đọc thành công! {len(df)} dòng")
        
        # Gán tên cột theo đúng vị trí
        df.columns = [
            'SKU',          # cột 0
            'TenSanPham',   # cột 1
            'dvt',          # cột 2
            'Ton_PLT',      # cột 3
            'DeXuat_co_san',# cột 4
            'BQ_ban_3D',    # cột 5
            'Ton',          # cột 6
            'SLTB'          # cột 7
        ]
        
        # Giữ lại các cột cần dùng
        df = df[['SKU', 'TenSanPham', 'Ton_PLT', 'DeXuat_co_san', 'BQ_ban_3D', 'Ton', 'SLTB']]
        
        st.subheader("Dữ liệu đầu vào (10 dòng đầu)")
        st.dataframe(df.head(10))
        
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
        st.stop()

    # Lọc bỏ dòng không có SLTB hoặc SLTB = 0
    df = df[df['SLTB'].notna() & (df['SLTB'] > 0)]
    if len(df) == 0:
        st.warning("Không có dữ liệu hợp lệ (SLTB > 0).")
        st.stop()

    df['CT'] = ct_input

    # Tính đề xuất, ưu tiên cột có sẵn nhưng không vượt tồn PLT
    df['DeXuat'] = df.apply(lambda row: tinh_de_xuat(
        row['SLTB'], 
        row['CT'], 
        row['Ton'], 
        row['Ton_PLT'], 
        row['DeXuat_co_san']
    ), axis=1)

    # Áp dụng lọc phi logic (có thể loại bỏ hoặc điều chỉnh)
    df['LoaiBo'] = False
    df['LyDoLoaiBo'] = ""
    df['DeXuatSauLoc'] = 0
    for idx, row in df.iterrows():
        loai_bo, ly_do, de_xuat_moi = loc_phi_logic(
            row['SLTB'], 
            row['Ton'], 
            row['DeXuat'], 
            row['Ton_PLT']
        )
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
        bat_thuong, ly_do = kiem_tra_bat_thuong(
            row['SLTB'], 
            row['Ton'], 
            row['CT'], 
            de_xuat, 
            row['Ton_PLT']
        )
        df_khong_loai.at[idx, 'BatThuong'] = bat_thuong
        df_khong_loai.at[idx, 'LyDo'] = ly_do

    df_hop_le = df_khong_loai[~df_khong_loai['BatThuong']]
    df_bat_thuong = df_khong_loai[df_khong_loai['BatThuong']]

    # Hiển thị các nhóm
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
                st.write(f"**Tồn cửa hàng:** {row['Ton']}")
                st.write(f"**Tồn PLT:** {row['Ton_PLT']}")
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
                    so_luong_moi = st.number_input("Sửa số lượng", min_value=0, max_value=int(row['Ton_PLT']), value=int(row['DeXuatSauLoc']), key=f"edit_{idx}")
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

    # Tạo đơn hàng
    if st.button("📦 Tạo đơn hàng cuối cùng"):
        quyet_dinh = st.session_state.get('quyet_dinh', {})
        final_rows = []
        for _, row in df_hop_le.iterrows():
            if row['DeXuatSauLoc'] > 0:
                final_rows.append({
                    'SKU': row['SKU'],
                    'TenSanPham': row['TenSanPham'],
                    'SoLuongDat': row['DeXuatSauLoc'],
                    'TrangThai': 'Tự động'
                })
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
