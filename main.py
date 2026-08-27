import pandas as pd
import streamlit as st
from datetime import datetime

# ========== 1. Hàm tính toán đề xuất ==========
def tinh_de_xuat(row):
    """Tính số lượng đề xuất đặt theo công thức cơ bản"""
    sltb = row['SLTB']
    ct = row['CT']
    ton = row['Ton']
    de_xuat = max(0, (sltb * ct) - ton)
    return de_xuat

# ========== 2. Hàm kiểm tra bất thường ==========
def kiem_tra_bat_thuong(row, de_xuat):
    """Trả về (có_bất_thường, lý do)"""
    sltb = row['SLTB']
    ton = row['Ton']
    ct = row['CT']
    ly_do = []

    # 1. Tồn kho quá nhiều so với nhu cầu bán
    if sltb > 0:
        so_ngay_ban_duoc = ton / sltb
        if so_ngay_ban_duoc > 10:
            ly_do.append(f"Tồn kho {ton} đủ bán trong {so_ngay_ban_duoc:.1f} ngày (quá nhiều)")

    # 2. Lượng đề xuất quá cao so với nhu cầu thực trong chu kỳ
    nhu_cau_toi_da = sltb * ct * 1.5
    if de_xuat > nhu_cau_toi_da:
        ly_do.append(f"Đề xuất {de_xuat} > {nhu_cau_toi_da:.1f} (vượt 1.5 lần nhu cầu thực)")

    return len(ly_do) > 0, "; ".join(ly_do)

# ========== 3. Giao diện Streamlit ==========
st.set_page_config(page_title="AI Đặt Hàng Siêu Thị", layout="wide", initial_sidebar_state="collapsed")
st.title("🛒 Trợ lý AI Đặt Hàng Siêu Thị")
st.markdown("Hệ thống tự động đề xuất số lượng đặt và cảnh báo khi có bất thường để bạn xác nhận.")

uploaded_file = st.file_uploader("Tải lên file dữ liệu CSV", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.subheader("Dữ liệu đầu vào")
    st.dataframe(df)

    # Tạo cột đề xuất
    df['DeXuat'] = df.apply(tinh_de_xuat, axis=1)

    # Kiểm tra bất thường
    df['BatThuong'] = False
    df['LyDo'] = ""
    for idx, row in df.iterrows():
        bat_thuong, ly_do = kiem_tra_bat_thuong(row, row['DeXuat'])
        df.at[idx, 'BatThuong'] = bat_thuong
        df.at[idx, 'LyDo'] = ly_do

    # Tách hai nhóm
    df_hop_le = df[~df['BatThuong']]
    df_bat_thuong = df[df['BatThuong']]

    # Hiển thị danh sách cần xác nhận
    st.markdown("---")
    st.subheader("⚠️ Danh sách cần xác nhận (bất thường)")

    if len(df_bat_thuong) > 0:
        for idx, row in df_bat_thuong.iterrows():
            with st.expander(f"{row['TenSanPham']} (SKU: {row['SKU']})"):
                st.write(f"**Số bán gần nhất:** {row['SoBan']}")
                st.write(f"**Tồn kho:** {row['Ton']}")
                st.write(f"**SLTB:** {row['SLTB']} / ngày")
                st.write(f"**Chu kỳ (CT):** {row['CT']} ngày")
                st.write(f"**Đề xuất ban đầu:** {row['DeXuat']}")
                st.warning(f"**Lý do cảnh báo:** {row['LyDo']}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    dong_y = st.button("✅ Đồng ý đặt", key=f"ok_{idx}")
                with col2:
                    bo_qua = st.button("❌ Bỏ qua", key=f"skip_{idx}")
                with col3:
                    so_luong_moi = st.number_input("Sửa số lượng", min_value=0, value=int(row['DeXuat']), key=f"edit_{idx}")

                if dong_y:
                    st.session_state.setdefault('quyet_dinh', {})[row['SKU']] = ('DONG_Y', row['DeXuat'])
                    st.success(f"Đã đồng ý đặt {row['DeXuat']} cho {row['TenSanPham']}")
                if bo_qua:
                    st.session_state['quyet_dinh'][row['SKU']] = ('BO_QUA', 0)
                    st.info(f"Đã bỏ qua {row['TenSanPham']}")
                if so_luong_moi != row['DeXuat'] and st.button("Cập nhật số lượng", key=f"update_{idx}"):
                    st.session_state['quyet_dinh'][row['SKU']] = ('SUA', so_luong_moi)
                    st.success(f"Đã cập nhật số lượng {so_luong_moi}")
    else:
        st.success("Không có sản phẩm bất thường. Tất cả đều hợp lệ!")

    # Hiển thị danh sách hợp lệ tự động đặt
    st.markdown("---")
    st.subheader("✅ Danh sách tự động đặt (hợp lệ)")

    if len(df_hop_le) > 0:
        df_hop_le_display = df_hop_le[['SKU', 'TenSanPham', 'Ton', 'SLTB', 'CT', 'DeXuat']]
        st.dataframe(df_hop_le_display)
    else:
        st.write("Không có sản phẩm nào được tự động đặt.")

    # Nút xuất đơn hàng cuối cùng
    if st.button("📦 Tạo đơn hàng cuối cùng"):
        quyet_dinh = st.session_state.get('quyet_dinh', {})

        final_rows = []
        # Thêm các sản phẩm hợp lệ (tự động đặt)
        for _, row in df_hop_le.iterrows():
            if row['DeXuat'] > 0:
                final_rows.append({
                    'SKU': row['SKU'],
                    'TenSanPham': row['TenSanPham'],
                    'SoLuongDat': row['DeXuat'],
                    'TrangThai': 'Tu dong'
                })

        # Thêm các sản phẩm bất thường đã được quyết định
        for sku, (action, qty) in quyet_dinh.items():
            if action == 'DONG_Y' or action == 'SUA':
                if qty > 0:
                    ten = df[df['SKU'] == sku]['TenSanPham'].values[0]
                    final_rows.append({
                        'SKU': sku,
                        'TenSanPham': ten,
                        'SoLuongDat': qty,
                        'TrangThai': 'Da xac nhan'
                    })

        if len(final_rows) > 0:
            df_final = pd.DataFrame(final_rows)
            st.subheader("📋 Đơn hàng cuối cùng")
            st.dataframe(df_final)
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Tải đơn hàng CSV", csv, "don_hang.csv", "text/csv")
        else:
            st.warning("Không có sản phẩm nào để đặt.")
else:
    st.info("Hãy tải lên file CSV để bắt đầu.")