# Cutting cho Frappe 16

App độc lập `cutting`, dùng chung master và Factory Device từ `factory_management`. Trang operator công khai là `/cutting`; quản trị dùng List/Form **Cutting Record**, **Cutting History** và Page **Cutting Reports** trong Desk. Giao diện dùng CSS/control mặc định của Desk, kèm stylesheet nhỏ cho popup chọn mã hàng, thị trường và màu.

## Cài bằng Pilot

- Frappe `>=16.53.0,<17.0.0`, Python 3.14 và `factory_management >=0.1.40,<0.2.0` đã cài trên site. Phiên bản này cần Product Variant.product_color và Product Color.
- Trong Pilot, thêm repo public `https://github.com/uzumaki2204/cutting-frappe`, chọn nhánh `version-16`, tên app `cutting`, rồi cài vào site đích.
- Nếu đã có Web Page hoặc Builder Page xuất bản tại `/cutting`, lưu bản sao và tắt xuất bản trang cũ trước. Installer báo xung đột thay vì sửa nội dung trang có sẵn.
- Chạy migrate và build assets theo quy trình Pilot, sau đó khởi động lại workload. Sao lưu database và public/private files trước khi cài/nâng cấp.
- Gán `Cutting Manager` cho người quản lý hoặc `Cutting Viewer` cho người xem báo cáo Desk. Gán `Cutting Report Reader` cho User/API token cần gọi API Summary tương thích .NET. App cấp quyền Select master cho Manager và Viewer; quyền sửa master tiếp tục do app Factory Management quản lý.
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

Mở `/cutting` (tiếng Việt) hoặc `/cutting?lang=en`. Form **Nhập Cutting** nằm ở card trái; chỉ gồm mã hàng, thị trường, màu, ID mã hàng và số lượng, không yêu cầu nhập mùa sản xuất. Card **Bản ghi đã lưu** ở bên phải có bộ lọc mã hàng, màu, thị trường, ngày và ID mã hàng, cùng phân trang 8 dòng mặc định. Danh sách đọc tối đa 200 bản ghi gần nhất của thiết bị hiện tại. Header có logo, nút toàn màn hình, trạng thái/kiểm tra kết nối và cài đặt thiết bị. Popup chọn mã hàng, thị trường và màu hiển thị thành lưới card; các màn hình quản trị tiếp tục dùng giao diện mặc định của Frappe Desk.

Dùng nút cài đặt thiết bị trên đầu trang để nhập hoặc quét Device ID do Admin cấp, rồi bấm **Kích hoạt**. Thiết bị phải tồn tại trong **Factory Device**, đã duyệt, đang hoạt động và được gán công ty. ID không tồn tại bị từ chối và không tạo bản ghi mới. Tên máy được đọc từ **Factory Device**, không lấy từ QR hoặc tablet. Site HTTP hiện tại chỉ hỗ trợ nhập ID thủ công vì camera trình duyệt cần ngữ cảnh an toàn. Không đưa API key/secret Administrator vào tablet.

Chỉ các biến thể đang hoạt động và có đủ sản phẩm, màu, size, thị trường mới xuất hiện. Bản ghi Cutting chỉ lưu mã hàng, màu, thị trường, ID mã hàng, số lượng và thời điểm phát sinh. Mã sự kiện được tạo riêng cho từng lần nhập; gửi lại cùng mã của cùng thiết bị không tạo bản ghi thứ hai.

Hàng đợi được lưu trong `localStorage`, riêng cho mỗi ID thiết bị. Tạo/sửa/xóa khi mất mạng vẫn được giữ khi tab đang mở và tự gửi lại khi kết nối trở về. Chỉ sửa hoặc xóa được bản ghi có ngày phát sinh hôm nay theo múi giờ site; thao tác ngoại tuyến được đồng bộ sau khi ngày đã đổi sẽ bị loại bỏ và dữ liệu gốc mới nhất từ máy chủ được tải lại. HTTP nội bộ không hỗ trợ service worker: đóng hoặc tải lại trang khi đang mất mạng sẽ không mở lại được app. Khi truy cập lại lúc có mạng, hàng đợi đã lưu tiếp tục được đồng bộ. Nút **Xóa cache** hỏi xác nhận rồi xóa toàn bộ dữ liệu Cutting trên trình duyệt, bao gồm hàng đợi chưa đồng bộ; dữ liệu ứng dụng khác được giữ nguyên.

Trước khi chuyển từ phần mềm .NET, đồng bộ hết hàng đợi trên URL cũ. App không sao chép SQL Server hoặc localStorage của origin cũ. CuttingAgent, ingest và báo cáo máy cắt không thuộc bản này.

## Dữ liệu và import

**Cutting Record** hỗ trợ Frappe **Data Import** với XLSX/CSV. Tải template từ DocType này; các Link dùng `name` của master trên site. `Product`, `Product Color`, `Market`, `Plan Code`, `Quantity` và `Occurred At` bắt buộc. Lịch sử có thể để trống `Factory Device`; khi thiếu thiết bị có thể nhập `Company` và `Device UID` nếu có. Đặt `Source = Import`. Import chỉ yêu cầu master tồn tại, cho phép master lịch sử đã ngừng hoạt động; API tablet luôn yêu cầu biến thể đang hoạt động.

`Occurred At` và các trường Datetime dùng giờ site theo quy ước Frappe; file Excel/CSV dùng giờ site dạng `YYYY-MM-DD HH:mm:ss`. API tablet nhận và trả `occurred_at` dạng ISO UTC, tự chuyển đổi ở biên API. Bản ghi import tạo một snapshot lịch sử `Import`. Không import trực tiếp `Cutting History`. Sửa, xóa mềm và khôi phục tạo lịch sử riêng. Người có quyền Frappe `Delete` được xóa cứng Cutting Record; thao tác này cũng xóa các snapshot Cutting History liên quan để tránh liên kết mồ côi. Người có quyền `Delete` trên Cutting History có thể xóa lịch sử trực tiếp; sửa lịch sử luôn bị chặn. Xóa thông thường qua Frappe được lưu trong **Deleted Document** để khôi phục.

Trong List **Cutting Record**, dùng nút **Thùng rác** để lọc bản ghi đã xóa. Mở form rồi dùng **Khôi phục**. Báo cáo chi tiết theo thời điểm phát sinh tối đa 7 ngày; báo cáo tổng hợp tối đa 31 ngày và nhóm theo thứ Hai đầu tuần, thiết bị, sản phẩm, thị trường, màu, mã kế hoạch. Ngày phát sinh được tính theo múi giờ site. Tổng hợp theo ngày tạo còn hỗ trợ nhóm theo sản phẩm, màu, thị trường.

## API và ngôn ngữ

Hợp đồng API chuẩn nằm trong `docs/openapi.json`; collection Postman được sinh từ hợp đồng này và bổ sung assertion. Các method hiện có trả envelope Frappe `message`. `GET /api/method/cutting.reporting.summary` nhận `OccurredOnFrom`, `OccurredOnTo`, `CompanyCode`, `SampleCode`, `EventNo`, `DeviceName` và trả trực tiếp envelope .NET `success/code/message/data/errors`. Method này chỉ đọc `Cutting Record` cùng master trên Frappe; kết quả gồm `metadata`, `columns`, `rows`, `rawRows`. Nó yêu cầu `Cutting Report Reader`, System Manager hoặc Administrator. API report và manager dùng quyền của User đăng nhập hoặc User sở hữu API key. Tablet dùng Factory Device đã duyệt, không dùng User token.

Sau khi Pilot cập nhật Cutting và chạy migrate, mở **API Documentation** trong Desk rồi chọn service **Cutting API** để xem và gọi thử Summary trên Swagger. Patch `add_summary_api_docs` tạo service và endpoint nếu chưa có; các chỉnh sửa của người dùng trên hai bản ghi này được giữ lại.

Catalog UTF-8 Việt/Anh dùng chung frontend/backend là `cutting/i18n.json`; nhãn DocType dùng `cutting/translations/*.csv`. Repo không chứa credential hoặc địa chỉ riêng của site.

API kích hoạt/kiểm tra Cutting dùng `Factory Device` có sẵn và giữ nguyên URL/payload cũ. API không gọi nhánh đăng ký có thể tạo thiết bị và không đổi tên do Admin cấp. Liên kết size được đọc từ metadata Product Variant để hỗ trợ cả `Size` cũ và `ProductSize` mới.

Cutting lấy mã và tên màu từ các trường `color_code` và `color_name` của `Product Color`, chỉ đưa màu đang hoạt động vào danh mục. Khi nâng cấp từ Cutting 0.1.5, patch migrate chuyển liên kết màu trong Cutting Record và Cutting History theo mã màu. Nếu không tìm được Product Color trùng mã duy nhất, migrate dừng và yêu cầu tạo master tương ứng trước khi chạy lại.

## Kiểm tra và phát hành

```bash
node --test tests/*.test.js
postman collection lint postman/collections/Cutting-API
bench --site <test-site> run-tests --app cutting
```

Chạy integration test trên site riêng đã cài `factory_management` và `cutting`. Test tạo master/thiết bị tạm trong transaction của test framework. Không chạy bộ test này trên site đang vận hành.

Source chuẩn tại `integrations/frappe/cutting` trong repo FactoryManagement. Khi phát hành, đồng bộ đúng nội dung thư mục app vào repo riêng, tăng phiên bản trong `pyproject.toml`, `cutting/__init__.py`, manifest và OpenAPI, commit rồi push nhánh `version-16`/tag tương ứng. Bản 0.1.32 yêu cầu Factory Management tối thiểu 0.1.40. Trên tablet, trang Cutting chiếm vừa chiều cao màn hình và chỉ vùng danh sách bản ghi cuộn dọc; bảng giữ tiêu đề khi cuộn. Popup cài đặt, xác nhận xóa cache và xác nhận xóa bản ghi đều hiển thị phía trên khi trang đang ở chế độ toàn màn hình; thao tác tablet chỉ sửa hoặc xóa mềm bản ghi có ngày phát sinh hôm nay theo giờ site. Xóa cứng từ Desk tuân theo quyền `Delete` của Frappe. Cài mới tạo schema trống; người dùng tự import dữ liệu nghiệp vụ sau.
