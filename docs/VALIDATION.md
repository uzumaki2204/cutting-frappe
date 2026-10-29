# Kiểm chứng bản 0.1.1

Ngày kiểm tra: 2026-10-29. Môi trường: Frappe 16.53.0, Python 3.14, Factory Management 0.1.29. Các kiểm tra có dữ liệu dùng site thử riêng, chỉ tạo dữ liệu giả.

- 9 integration test đạt: gửi lại sự kiện, rollback lô lỗi, thiết bị chưa duyệt, master/variant ngừng hoạt động, lịch sử chỉ ghi thêm, xóa/khôi phục, import thiếu thiết bị, quyền Data Import của manager, giới hạn báo cáo và chuyển đổi UTC/giờ site.
- 7 test hàng đợi JavaScript đạt, gồm sửa/xóa trong lúc request đang gửi và bảo toàn thay đổi chưa đồng bộ.
- Postman Tablet: 6 request, 16 assertion đạt. Collection 14 request lint không lỗi/cảnh báo.
- Native Data Import: CSV và XLSX tạo bản ghi thiếu thiết bị thành công; Link sản phẩm không tồn tại bị từ chối. XLSX được kiểm tra qua File upload như Desk; CLI XLSX của bản Frappe đang chạy có lỗi đọc binary nên không dùng đường CLI cho XLSX.
- Đã thao tác tablet tạo/sửa/xóa, Desk khôi phục và xem đủ Create/Update/Delete/Restore; trang báo cáo và form Data Import mở được bằng role Cutting Manager.
- Đã xem giao diện ở 390×844, 1024×768 và 1440×900. Không tràn ngang toàn trang; bảng cuộn bên trong. Nhãn input đầy đủ, focus bàn phím có viền mặc định. Tỷ lệ tương phản đo được: nhãn 7.81:1, nút chính 17.93:1, trạng thái xanh 4.54:1.
- Đã nhập khi offline với tab còn mở, kiểm tra hàng đợi được giữ trong localStorage, trở lại online tự gửi thành công và hàng đợi về 0. Không hỗ trợ mở lại trang khi offline trên HTTP.
- Package wheel, build assets, migrate lặp lại và smoke test sau cài đạt. Smoke tạo tablet/import mẫu, kiểm tra idempotency/lịch sử/báo cáo rồi rollback toàn bộ.

Khi site có trang Builder hoặc Web Page cũ tại `/cutting`, cần tắt xuất bản trang cũ trước để URL đi vào app. Installer phát hiện xung đột; không ghi đè nội dung trang cũ. Không chuyển dữ liệu SQL hoặc hàng đợi của phần mềm cũ.

- Form nhập ở cột trái, bảng bản ghi ở cột phải; đăng ký/kiểm tra thiết bị nằm trong hộp thoại mở từ nút cài đặt trên đầu trang.

## Cập nhật giao diện 0.1.2

- Form tablet giống luồng cũ: mã hàng, thị trường, màu, ID mã hàng và số lượng; không có trường mùa sản xuất.
- Danh sách hiển thị tối đa 200 bản ghi gần nhất của thiết bị, không giới hạn trong ngày hiện tại. Bộ lọc gồm mã hàng, màu, thị trường, khoảng ngày và ID mã hàng; phân trang bắt đầu ở 8 dòng.
- Thêm logo Kim Thanh Group và icon toàn màn hình, kết nối, cài đặt thiết bị. Card nhập và card bản ghi phân biệt bằng utility class mặc định của Desk; không thêm CSS riêng.
- Đã xem trang đang chạy ở 267×844, 390×844, 1024×768 và 1440×900; không tràn ngang. Toàn màn hình bật/tắt, nút kết nối kiểm tra được API, hộp thoại thiết bị mở/đóng và trả focus đúng.
- Đã thao tác bộ lọc ID, mã hàng và phân trang bằng dữ liệu giả chỉ trong localStorage của browser offline; không gửi bản ghi lên site. Không chạy lại bộ test tự động cho thay đổi giao diện này.

## Khắc phục tải JavaScript 0.1.3

- Gắn phiên bản package vào URL của hai script tablet để trình duyệt tải asset mới sau khi cập nhật app, thay vì tiếp tục dùng script cũ từ cache.
- Render sẵn lựa chọn mặc định cho các dropdown để trang không hiện ô trống khi JavaScript chưa khởi tạo.
- Kiểm tra thao tác trên trang đang chạy: mở hộp thoại cài đặt thiết bị, nút kết nối và toàn màn hình; xác nhận asset được tải với query version mới và không phát sinh lỗi JavaScript.

## Popup thiết bị 0.1.5

- Sao lưu site Pilot gồm database, cấu hình và public/private files trước khi xóa DocType tùy chỉnh `Cutting Device` cùng bản ghi thử. Xác nhận DocType đã hết và các `Factory Device` vẫn giữ nguyên.
- Popup dùng `frappe.ui.Dialog` và `controls.bundle.js` trên trang public; không có CSS riêng. Đã kiểm tra trang không có lỗi JavaScript, popup ở desktop và viewport mobile 390×844 không tràn ngang, nút đóng trả focus về nút cài đặt.
- Kiểm tra trên site: ID không tồn tại trả 404 và không tạo thiết bị; thiết bị Pending trả 403 và Device ID đang lưu không đổi. Smoke giao dịch rollback xác nhận Pending, inactive, thiếu công ty bị từ chối; thiết bị hợp lệ kích hoạt và tải bootstrap; sync, import mẫu, lịch sử và báo cáo vẫn đạt. Sau smoke, các `Factory Device` vận hành vẫn giữ nguyên.
- Postman: request ID không tồn tại đạt 2 assertion, collection 15 request lint sạch. 9 test JavaScript đạt cho hàng đợi, QR UUID/JSON/URL và xóa cache có phạm vi Cutting. Wheel `0.1.5` build thành công.
- Kiểm tra toast lỗi tiếng Việt và tiếng Anh; `Quét QR` trên HTTP báo camera không khả dụng và cho nhập tay. Trên browser mô phỏng secure context/camera, QR JSON điền đúng ID nhưng không tự kích hoạt. Chưa kiểm tra camera vật lý qua HTTPS.
- Xóa cache: hủy giữ nguyên dữ liệu; xác nhận xóa cả hàng đợi Cutting chưa đồng bộ và giữ khóa localStorage ứng dụng khác. Admin cần cấu hình/duyệt `Factory Device` trước khi kích hoạt vận hành.
