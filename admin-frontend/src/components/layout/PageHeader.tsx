import { ReactNode } from "react";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";

export default function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <ContentLayout
      header={
        <Header variant="h1" description={description} actions={actions}>
          {title}
        </Header>
      }
    >
      {children}
    </ContentLayout>
  );
}
