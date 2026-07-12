import { Card, Col, Row, Statistic, Typography } from "antd";

export function DashboardPage() {
  return (
    <div>
      <Typography.Title level={3}>Сводка</Typography.Title>
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic title="Продажи сегодня" value={0} suffix="сум" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Чеков сегодня" value={0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Товаров в каталоге" value={0} />
          </Card>
        </Col>
      </Row>
      <Typography.Paragraph type="secondary" style={{ marginTop: 24 }}>
        Каркас MVP. Дальше: касса (POS), приёмка на склад и голосовой ввод товаров.
      </Typography.Paragraph>
    </div>
  );
}
