# Cutting cho Frappe 16

App độc lập `cutting`, dùng chung master và Factory Device từ `factory_management`. Trang operator công khai là `/cutting`; quản trị dùng List/Form **Cutting Record**, **Cutting History** và Page **Cutting Reports** trong Desk. Giao diện dùng CSS/control mặc định của Desk; app không có CSS tùy biến.

## Cài bằng Pilot

- Frappe `>=16.53.0,<17.0.0`, Python 3.14 và `factory_management >=0.1.29,<0.2.0` đã cài trên site.
- Trong Pilot, thêm repo public `https://github.com/uzumaki2204/cutting-frappe`, chọn nhánh `version-16`, tên app `cutting`, rồi cài vào site đích.
- Nếu đã có Web Page hoặc Builder Page xuất bản tại `/cutting`, lưu bản sao và tắt xuất bản trang cũ trước. Installer báo xung đột thay vì sửa nội dung trang có sẵn.
- Chạy migrate và build assets theo quy trình Pilot, sau đó khởi động lại workload. Sao lưu database và public/private files trước khi cài/nâng cấp.
- Gán `Cutting Manager` cho người quản lý hoặc `Cutting Viewer` cho người chỉ xem báo cáo. App cấp quyền Select master cho hai role này; quyền sửa master tiếp tục do app Factory Management quản lý.
- `Cutting Manager` được tạo và xử lý Data Import do chính mình sở hữu; Frappe tiếp tục kiểm tra quyền import của DocType đích.

Với Bench thông thường:

```bash
bench get-app --branch version-16 cutting https://github.com/uzumaki2204/cutting-frappe.git
bench --site <site> install-app cutting
bench --site <site> migrate
bench build --app cutting
bench restart
```

App không cần Server Scripts. Schema là DocType chuẩn được quản lý trong source; Custom Field và Property Setter của Frappe vẫn là lớp tùy chỉnh của site. Các lần migrate chỉ bổ sung quyền Select còn thiếu, không ghi đè bản ghi master, tài khoản hay phân công role.

## Tablet

Mở `/cutting` (tiếng Việt) hoặc `/cutting?lang=en`. Form **Nhập Cutting** nằm ở cột trái, bản ghi nằm bên phải. Dùng nút **Cài đặt thiết bị** trên đầu trang để đăng ký hoặc kiểm tra UUID, rồi duyệt thiết bị trong **Factory Device**, bật hoạt động và gán công ty. Tablet dùng ID của thiết bị theo cùng cơ chế QC/UQQC; ID không phải bí mật. Không đưa API key/secret Administrator vào tablet.

Chỉ các biến thể đang hoạt động và có đủ sản phẩm, màu, size, thị trường mới xuất hiện. Bản ghi Cutting chỉ lưu sản phẩm, màu, thị trường, mã kế hoạch, số lượng và thời điểm phát sinh. Mã sự kiện được tạo riêng cho từng lần nhập; gửi lại cùng mã của cùng thiết bị không tạo bản ghi thứ hai.

Hàng đợi được lưu trong `localStorage`, riêng cho mỗi ID thiết bị. Tạo/sửa/xóa khi mất mạng vẫn được giữ khi tab đang mở và tự gửi lại khi kết nối trở về. HTTP nội bộ không hỗ trợ service worker: đóng hoặc tải lại trang khi đang mất mạng sẽ không mở lại được app. Khi truy cập lại lúc có mạng, hàng đợi đã lưu tiếp tục được đồng bộ. Không xóa dữ liệu browser khi còn hàng đợi.

Trước khi chuyển từ phần mềm .NET, đồng bộ hết hàng đợi trên URL cũ. App không sao chép SQL Server hoặc localStorage của origin cũ. CuttingAgent, ingest và báo cáo máy cắt không thuộc bản này.

## Dữ liệu và import

**Cutting Record** hỗ trợ Frappe **Data Import** với XLSX/CSV. Tải template từ DocType này; các Link dùng `name` của master trên site. `Product`, `Color`, `Market`, `Plan Code`, `Quantity` và `Occurred At` bắt buộc. Lịch sử có thể để trống `Factory Device`; khi thiếu thiết bị có thể nhập `Company` và `Device UID` nếu có. Đặt `Source = Import`. Import chỉ yêu cầu master tồn tại, cho phép master lịch sử đã ngừng hoạt động; API tablet luôn yêu cầu biến thể đang hoạt động.

`Occurred At` và các trường Datetime dùng giờ site theo quy ước Frappe; file Excel/CSV dùng giờ site dạng `YYYY-MM-DD HH:mm:ss`. API tablet nhận và trả `occurred_at` dạng ISO UTC, tự chuyển đổi ở biên API. Bản ghi import tạo một snapshot lịch sử `Import`. Không import trực tiếp `Cutting History`. Sửa, xóa mềm và khôi phục tạo lịch sử riêng; xóa vật lý bản ghi và chỉnh sửa lịch sử bị chặn.

Trong List **Cutting Record**, dùng nút **Thùng rác** để lọc bản ghi đã xóa. Mở form rồi dùng **Khôi phục**. Báo cáo chi tiết theo thời điểm phát sinh tối đa 7 ngày; báo cáo tổng hợp tối đa 31 ngày và nhóm theo thứ Hai đầu tuần, thiết bị, sản phẩm, thị trường, màu, mã kế hoạch. Ngày phát sinh được tính theo múi giờ site. Tổng hợp theo ngày tạo còn hỗ trợ nhóm theo sản phẩm, màu, thị trường.

## API và ngôn ngữ

Hợp đồng API chuẩn nằm trong `docs/openapi.json`; collection Postman được sinh từ hợp đồng này và bổ sung assertion. Mọi method trả envelope Frappe `message`. API report và manager dùng quyền của User đăng nhập hoặc User sở hữu API key. Tablet dùng Factory Device đã duyệt, không dùng User token.

Catalog UTF-8 Việt/Anh dùng chung frontend/backend là `cutting/i18n.json`; nhãn DocType dùng `cutting/translations/*.csv`. Repo không chứa credential hoặc địa chỉ riêng của site.

Adapter đăng ký/kiểm tra thiết bị gọi API dùng chung trên bản Factory Management mới. Với bản cũ có token riêng của QC, adapter chỉ đăng ký Factory Device ở trạng thái Pending và dùng cùng phê duyệt chung; không tạo QC client, token hoặc quyền QC. Liên kết size được đọc từ metadata Product Variant để hỗ trợ cả `Size` cũ và `ProductSize` mới.

Nếu site dùng DocType `Color` chuẩn chưa có `color_code`, `color_name` hoặc `is_active`, Cutting dùng tên bản ghi làm mã/nhãn và coi màu đó là đang hoạt động. Khi các trường này có sẵn, Cutting dùng đúng mã, tên và cờ hoạt động của master.

## Kiểm tra và phát hành

```bash
node --test tests/client-core.test.js
postman collection lint postman/collections/Cutting-API
bench --site <test-site> run-tests --app cutting
```

Chạy integration test trên site riêng đã cài `factory_management` và `cutting`. Test tạo master/thiết bị tạm trong transaction của test framework. Không chạy bộ test này trên site đang vận hành.

Source chuẩn tại `integrations/frappe/cutting` trong repo FactoryManagement. Khi phát hành, đồng bộ đúng nội dung thư mục app vào repo riêng, tăng phiên bản trong `pyproject.toml`, `cutting/__init__.py`, manifest và OpenAPI, commit rồi push nhánh `version-16`/tag tương ứng. Cài mới tạo schema trống; người dùng tự import dữ liệu nghiệp vụ sau.
