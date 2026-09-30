# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95Breach`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Primary SLO `fast_successful_requests` (`response_sent.latency_ms <= 3000ms` đạt 99.5% trong 28 ngày)
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 3000` duy trì liên tục trong `5m`
- Ảnh hưởng tới người dùng: Người dùng phải chờ phản hồi lâu hơn ngưỡng cam kết (> 3 giây), gây trải nghiệm hội thoại bị giật/chậm và đốt cháy error budget của SLO.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Mở panel `Latency percentiles and TTFT` trên dashboard để xác nhận thời điểm `p95`/`p99` tăng vọt và đối chiếu với `ttft_p95` xem độ trễ nằm trước hay trong bước sinh token.
  2. **Logs:** Lọc `data/logs.jsonl` trong khoảng thời gian phát cảnh báo với điều kiện `event == "response_sent"` và `latency_ms > 3000`, lấy `correlation_id` của một request tiêu biểu.
  3. **Traces:** Tìm trace có cùng `correlation_id` trên Langfuse, mở waterfall của `lab-agent-run` để so sánh thời gian chạy của span `retrieval` và `generation` nhằm xác định chính xác bước gây nghẽn.
- Mitigation tạm thời: Nếu span `retrieval` chậm bất thường, tắt kịch bản lỗi/giảm tải vector store (`POST /incidents/rag_slow/disable` hoặc bật cache/fallback context); nếu `generation` chậm do prompt mới quá dài, rollback label `production` trên Langfuse về version trước đó.
- Owner: `student-2A202602368`

## Alert 2

- Tên: `HighErrorRateOrRetrievalFailure`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Guardrail `error_rate_pct_max <= 2%`, `retrieval_success_rate_pct_min >= 90%` và Primary SLO `fast_successful_requests`
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` hoặc `tool_success_rate_pct < 90%` duy trì trong `5m`
- Ảnh hưởng tới người dùng: Người dùng nhận lỗi HTTP 500 hoặc câu trả lời thiếu tài liệu tham chiếu từ RAG, làm gián đoạn trực tiếp chức năng hỏi đáp/tóm tắt.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Mở panel `Error rate and retrieval success` trên dashboard để xem tỉ lệ lỗi tổng thể, phân bố `error_type` và tỉ lệ `tool_success_rate_pct`.
  2. **Logs:** Truy vấn `data/logs.jsonl` các bản ghi có `event == "request_failed"` hoặc `tool_success == false` trong cửa sổ sự cố, ghi nhận `correlation_id`, `error_type` và `payload.detail`.
  3. **Traces:** Tra cứu `correlation_id` trên Langfuse để kiểm tra span bị đánh dấu lỗi (`retrieval` hoặc `generation`), đối chiếu exception/status message và `prompt_version`.
- Mitigation tạm thời: Khôi phục kết nối vector store hoặc tắt chế độ fault injection (`POST /incidents/tool_fail/disable`), kích hoạt cơ chế fallback trả lời an toàn khi retrieval timeout để không làm sập toàn bộ request `/chat`.
- Owner: `student-2A202602368`

## Alert 3

- Tên: `CostSpikeOrQualityDrop`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Guardrails `daily_cost_usd_max <= 2.5 USD` và `quality_score_avg_min >= 0.75`
- Điều kiện và thời gian duy trì: Tổng chi phí 24h `sum(cost_usd) > 2.5` hoặc điểm chất lượng trung bình `mean(quality_score) < 0.75` duy trì trong `10m`
- Ảnh hưởng tới người dùng: Chất lượng câu trả lời suy giảm (thiếu thông tin trọng tâm hoặc bị che PII không mong muốn) hoặc hệ thống tiêu thụ lượng token/chi phí vượt ngân sách vận hành.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Kiểm tra 3 panel `Cost over time`, `Input and output tokens` và `Quality proxy` để xác định thời điểm chi phí/token tăng đột biến hoặc `quality_score` tụt dưới `0.75`.
  2. **Logs:** Lọc các dòng `event == "response_sent"` trong `data/logs.jsonl` có `cost_usd` cao bất thường, `tokens_out` lớn hoặc `quality_score < 0.75` để lấy `correlation_id` và `feature`.
  3. **Traces:** Mở trace tương ứng với `correlation_id` trên Langfuse, kiểm tra metadata `prompt_name`, `prompt_label`, `prompt_version` trên `lab-agent-run` và `usage_details`/`cost_details` trên span `generation`.
- Mitigation tạm thời: Nếu sự cố xảy ra ngay sau khi promote prompt mới, thực hiện rollback label `production` trên Langfuse về version ổn định trước đó (`v1`); nếu do kịch bản `cost_spike`, tắt qua `POST /incidents/cost_spike/disable` và giới hạn `max_tokens`.
- Owner: `student-2A202602368`

