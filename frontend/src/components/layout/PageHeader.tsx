import { ReactNode } from "react";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";

// One place to set the standard page chrome — header, description slot,
// action slot — so pages don't each reinvent the ContentLayout dance.
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
