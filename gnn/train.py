import time
import numpy as np
import torch as th
import torch.nn.functional as F
from sklearn.model_selection import StratifiedKFold


from gnn.eval import performance, evaluate
from gnn.wtagnn import WTAGNN
from graph.graph import GraphLoader

def start_train(args):
    gloader = GraphLoader()
    g, nf, ef, e_label, train_mask, test_mask, val_mask = gloader.load_graph(args)  

    n_classes = 2
    n_edges = g.number_of_edges()
    input_node_feat_size, input_edge_feat_size = nf.shape[1], ef.shape[1]

    print('\n************initilize model************')
    # create WTAGNN model
    model = WTAGNN(g, input_node_feat_size, input_edge_feat_size, 
                   args.n_hidden, n_classes, args.n_layers,  F.relu, args.dropout)
    print(model)

    # apply cuda()
    if args.gpu < 0:
        cuda = False
    else:
        cuda = True
        print('using gpu:', args.gpu)
        th.cuda.empty_cache()
        th.cuda.set_device(args.gpu)
        nf, ef, e_label = nf.cuda(), ef.cuda(), e_label.cuda()
        train_mask, val_mask, test_mask = train_mask.cuda(), val_mask.cuda(), test_mask.cuda()
        model.cuda()

    loss_fcn = th.nn.CrossEntropyLoss()
    # use optimizer
    optimizer = th.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    # start training
    print('\n************start training************')
    dur, max_acc = [], -1
    for epoch in range(args.n_epochs):
        model.train()
        t0 = time.time()
        # forward
        n_logits, e_logits = model(nf, ef)
        loss = loss_fcn(e_logits[train_mask], e_label[train_mask])

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        dur.append(time.time() - t0)

        acc, predictions, labels = evaluate(model, g, nf, ef, e_label, val_mask)

        # save the best model
        if acc > max_acc:
            max_acc = acc
            th.save(model.state_dict(), './output/best.model.' + args.model_name)

        print("Epoch {:05d} | Time(s) {:.4f} | Loss {:.4f} | Accuracy {:.4f} | "
              "ETputs(KTEPS) {:.2f}". format(epoch, dur[-1], loss.item(),
                                             acc, n_edges / np.mean(dur) / 1000))

    print("Inference time: avg time {:.4f}, stdev time {:.4f}".format(np.mean(dur), np.std(dur)))

    # load the best model
    best_model = WTAGNN(g, input_node_feat_size, input_edge_feat_size, args.n_hidden, n_classes, 
                args.n_layers,  F.relu, args.dropout)
    if cuda:
        best_model.cuda()
    best_model.load_state_dict(th.load( './output/best.model.' + args.model_name))

    acc, predictions, labels = evaluate(best_model, g, nf, ef, e_label, test_mask)
    precision, recall, tnr, tpr, f1 = performance(predictions.tolist(), labels.tolist(), acc)

def start_train_cv(args):
    gloader = GraphLoader()
    g, nf, ef, e_label, _, _, _ = gloader.load_graph(args)  

    n_classes = 2
    n_edges = g.number_of_edges()
    input_node_feat_size, input_edge_feat_size = nf.shape[1], ef.shape[1]

    if args.gpu < 0:
        cuda = False
    else:
        cuda = True
        print('using gpu:', args.gpu)
        th.cuda.empty_cache()
        th.cuda.set_device(args.gpu)
        nf, ef = nf.cuda(), ef.cuda()

    print('\n************start training for {:d} folds************'.format(args.fold))
    kf = StratifiedKFold(n_splits=args.fold, shuffle=True)
    kf.get_n_splits()
    print(kf)
    fold = 0
    total_precision = total_acc = total_recall = 0
    for train_index, test_index in kf.split(e_label, e_label):
        fold += 1
        print('\nfold #: ', str(fold))
        train_mask = np.zeros(e_label.shape[0])
        train_mask[train_index] = 1
        train_mask = th.BoolTensor(train_mask)

        test_mask= np.zeros(e_label.shape[0])
        test_mask[test_index] = 1
        test_mask = th.BoolTensor(test_mask)

        # create WTAGNN model
        model = WTAGNN(g, input_node_feat_size, input_edge_feat_size, args.n_hidden, 
                       n_classes, args.n_layers,  F.relu, args.dropout)
        print(model)

        # apply cuda()
        if cuda:
            e_label = e_label.cuda()
            train_mask = train_mask.cuda()
            test_mask = test_mask.cuda()
            model.cuda()

        loss_fcn = th.nn.CrossEntropyLoss()
        # use optimizer
        optimizer = th.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

        dur = []; max_acc = -1
        for epoch in range(args.n_epochs):
            model.train()
            if epoch >= 3: t0 = time.time()
            # forward
            n_logits, e_logits = model(nf, ef)

            loss = loss_fcn(e_logits[train_mask], e_label[train_mask])

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if epoch >= 3:
                dur.append(time.time() - t0)

            acc, predictions, labels = evaluate(model, g, nf, ef, e_label, test_mask)
            # save the best model
            if acc > max_acc:
                max_acc = acc
                th.save(model.state_dict(), './output/best.model.' + args.model_name + '.fold.' + str(fold))

            print("Epoch {:05d} | Time(s) {:.4f} | Loss {:.4f} | Accuracy {:.4f} | "
                "ETputs(KTEPS) {:.2f}". format(epoch, np.mean(dur), loss.item(),
                                                acc, n_edges / np.mean(dur) / 1000))

        # load the best model
        best_model = WTAGNN(g, input_node_feat_size, input_edge_feat_size, args.n_hidden, n_classes, 
                            args.n_layers,  F.relu, args.dropout)
        if cuda:
            best_model.cuda()
        best_model.load_state_dict(th.load('./output/best.model.' + args.model_name + '.fold.' + str(fold)))

        acc, predictions, labels = evaluate(best_model, g, nf, ef, e_label, test_mask)

        precision, recall, tnr, tpr, f1 = performance(predictions.tolist(), labels.tolist(), acc)

        total_precision += precision
        total_acc += acc
        total_recall += recall

    print('\n************training done! Averaged model performance************')
    print('acc/pre/rec: ', str("{:.2f}".format(total_acc/ args.fold* 100) ) + '%/' 
                         + str("{:.2f}".format(total_precision / args.fold* 100) ) + '%/' +
                           str("{:.2f}".format(total_recall/args.fold* 100) ) + '%')

