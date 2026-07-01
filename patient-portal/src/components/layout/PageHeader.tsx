import { ReactNode } from "react";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";

interface Props {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export default function PageHeader({ title, description, actions, children }: Props) {
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
